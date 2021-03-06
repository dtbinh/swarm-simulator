# sarsim.particle.base
# A Particle class for local behaviors
#
# Author:   Benjamin Bengfort <benjamin@bengfort.com>
# Created:  Tue Apr 15 10:50:20 2014 -0400
#
# Copyright (C) 2014 Bengfort.com
# For license information, see LICENSE.txt
#
# ID: base.py [] benjamin@bengfort.com $

"""
A Particle class for local behaviors
"""

##########################################################################
## Imports
##########################################################################

import numpy as np

from swarm.params import *
from swarm.exceptions import *
from swarm.vectors import Vector

##########################################################################
## Module Constants
##########################################################################

## Possible states
SPREADING = "spreading"
SEEKING   = "seeking"
CARAVAN   = "caravan"
GUARDING  = "guarding"
STUNNED   = "stunned"

## Maximum Velocity
VMAX      = float(world_parameters.get('maximum_velocity'))
VMAX2     = VMAX*VMAX

##########################################################################
## Particle Object
##########################################################################

class Particle(object):

    def __init__(self, position, velocity, identifier=None, **kwargs):
        """
        Initialize a particle by assigning a position and velocity to it.
        Optional parameters include assigning an idx value (a unique way
        to identify the particle) and the world it belongs to, so that it
        can be bound to discover its own neighborhood.
        """
        self.params = kwargs.get('params', world_parameters)

        self.pos    = Vector.arr(position)           # Init vectors here?
        self.vel    = Vector.arr(velocity)           # Init vectors here?
        self.idx    = identifier
        self.world  = kwargs.get('world', None)      # Initialize in world
        self.state  = kwargs.get('state', SPREADING) # Set initial state...
        self.team   = kwargs.get('team', 'ally')     # Set the team
        self.home   = kwargs.get('home', None)       # Remember where home is
        self.memory = []                             # Initialize the memory
        self.target = None                           # Initialize target
        self.loaded = False                          # Are we carrying minerals or not?
        self.enemy  = "enemy" if self.team == "ally" else ("ally" if self.team == "enemy" else None)
        self.stun_cooldown = 0

        # Hidden variables to reduce computation complexity
        self._pos    = None                          # Holder for new position
        self._vel    = None                          # Holder for new velocity
        self._state  = None                          # Holder for new state
        self._target = None                          # Holder for new target
        self._loaded = None                          # Holder for loaded state
        self._neighbors = None                       # Holder for neighbors in RMAX

    def __repr__(self):
        type_name  = self.__class__.__name__
        identifier = self.idx or "anonymous"
        if self.world:
            return "<bound %s %s of %r>" % (type_name, identifier, self.world)
        return "<unbound %s %s>" % (type_name, identifier)

    ##////////////////////////////////////////////////////////////////////
    ## Particle Methods
    ##////////////////////////////////////////////////////////////////////

    def update(self):
        """
        Called to update the particle at a new timestep.
        """

        self.update_velocity()
        self.update_position()
        self.update_state()

    def update_position(self):
        """
        Adds the velocity to get a new position, also ensures a periodic
        world by using modulo against the width and height of the world.
        """

        if self.state == STUNNED:
            self._pos = self.pos
            return

        newpos = self.pos + self._vel
        x = newpos.x % self.world.size[0]
        y = newpos.y % self.world.size[1]
        self._pos = Vector.arrp(x,y)

    def update_velocity(self):
        """
        Instead of starting with velocity zero as in the ARod paper, we
        implement 'inertia' by using the old velocity.
        """

        if self.state == STUNNED:
            self._vel = self.vel
            return

        vectors = []    # Tuples of vector components and their priority
        for component, parameters in self.components.items():
            # Get the method by name and compute
            if hasattr(self, component):
                velocity = getattr(self, component)
                vectors.append((component, velocity(), parameters))
            else:
                raise Exception("No method on %r, '%s'" % (self, component))

        newvel = self.vel
        for comp, vec, params in vectors:
            newvel = newvel + (params.weight * vec)

        if newvel.length2 > VMAX2:
            newvel = VMAX * newvel.unit

        self._vel = newvel

    def update_state(self):
        """
        Uses the finite state machine to update the current state.
        Currently implementing the non-guarding flock

        TODO: Have mineral sight distance be in config
        TODO: Have this part be evolutionary ...
        """

        # Initially, we just remain in our current state.
        self._state  = self.state
        self._target = self.target
        self._loaded = self.loaded

        if self.state != STUNNED:
            enemy = self.find_nearest(30, 360, team=self.enemy, except_state=STUNNED)
            if enemy:
                self._state = STUNNED
                angle = (enemy.pos - self.pos).angle(self.vel)
                self.stun_cooldown = (180 - angle) / 1
                return

        if self.state == STUNNED:
            self.stun_cooldown -= 1
            if self.stun_cooldown <= 0:
                if self.target == self.home:
                    self._state = CARAVAN if self.loaded else GUARDING
                else:
                    self._state = SPREADING
                return

        if self.state == SPREADING:
            # scan for mineral stashes
            for mineral in [m for m in self.neighbors(200, 360, team='mineral') if m != self.home and m.stash > 0 and m not in self.memory]:
                self.memory.append(mineral)

            if len(self.memory) > 0:
                self._target = self.memory[-1]
                self._state  = SEEKING
                return

        if self.state == SEEKING:
            if self.pos.distance2(self.target.relative_pos(self.pos)) < 900:
                if self.target.stash > 0:
                    if self.target.idx != (self.enemy + '_home') and \
                            len([n for n in self.neighbors(200, 360, team=self.team) if n.state == GUARDING or n._state == GUARDING]) < self.params.depo_guard_threshold:
                        self._state = GUARDING
                        return
                    else:
                        self._loaded = self.target.mine()
                        self._target = self.home
                        self._state  = CARAVAN
                        return
                else:
                    self.memory.remove(self._target)
                    self._target = None
                    self._state  = SPREADING
                    return

        if self.state == CARAVAN:
            if self.pos.distance2(self.target.relative_pos(self.pos)) < 100:
                self.target.drop()
                self._loaded = False

                guards = [n for n in self.neighbors(200, 360, team=self.team) if n.state == GUARDING or n._state == GUARDING]
                if len(guards) < self.params.home_guard_threshold:
                    self._state = GUARDING
                    return
                else:
                    if self.memory:
                        self._target = self.memory[-1]
                        self._state  = SEEKING
                        return
                    else:
                        self._target = None
                        self._state  = SPREADING
                        return

        if self.state == GUARDING:
            if self.target.stash <= 0:
                self._state = SPREADING
                return

    def blit(self):
        """
        Swap new pos/vel for old ones.
        """
        if world_parameters.debug:
            print "Particle %s" % self.idx
            print "Position: %s --> %s" % (self.pos, self._pos)
            print "Velocity: %s --> %s" % (self.vel, self._vel)
            print "State:    %s --> %s" % (self.state, self._state)
            print "Target:   %s --> %s" % (self.target, self._target)
            print "Loaded:   %s --> %s" % (self.loaded, self._loaded)
            print
        self.pos     = self._pos
        self.vel     = self._vel
        self.state   = self._state
        self.target  = self._target
        self.loaded  = self._loaded
        self._pos    = None
        self._vel    = None
        self._state  = None
        self._target = None
        self._loaded = None
        self._neighbors = None

    def copy(self):
        """
        Returns an unbound copy of the particle without its memory.
        """
        return self.__class__(
            self.pos.copy(), self.vel.copy(), self.idx,
            team=self.team, state=self.state, home=self.home,
        )

    ##////////////////////////////////////////////////////////////////////
    ## Helper Functions
    ##////////////////////////////////////////////////////////////////////

    @property
    def components(self):
        """
        Get movement behaviors components based on state
        """
        _behavior = self.params.get(self.state)
        if _behavior is None:
            raise ImproperlyConfigured("No movement behaviors for state '%s'." % self.state)
        return _behavior.components

    def is_bound(self):
        """
        Returns the bound state of the particle.
        """
        if not self.world: return False
        return True

    def in_sight(self, point, radius, alpha):
        """
        Determines whether or not another point (Vector) is in sight of the
        current particule based on a given radius and alpha.
        """
        radius2 = radius * radius
        delta = point - self.pos
        if delta.length2 > radius2: return False # The distance is outside the vision radius

        angle = self.vel.angle(delta)
        alpha = alpha / 2
        if angle > alpha: return False         # The angle is outside our vision angle from heading

        return True

    def relative_pos(self, point):
        size_x = self.world.size[0]
        size_y = self.world.size[1]
        rel_x = self.pos.x
        rel_y = self.pos.y
        if (abs(self.pos.x - point.x) > size_x / 2):
            rel_x += (-1 if (self.pos.x - point.x) > 0 else 1) * size_x
        if (abs(self.pos.y - point.y) > size_y/ 2):
            rel_y += (-1 if (self.pos.y - point.y) > 0 else 1) * size_y
        return Vector.arrp(rel_x, rel_y)

    def neighbors(self, radius, alpha, team='any', source='internal'):
        """
        Finds the neighbors given a radius and an alpha

        Only checks neighbors that are within RMAX (the maximum radius of
        any movement component), therefore only evaluates the entire agent
        space once per update rather than for every movmement behavior.
        """

        if not self.is_bound():
            raise Exception("Can only find neighbors for bound particles.")

        if source=='internal' and self._neighbors is None:
            self._neighbors = list(self.neighbors(self.params.max_radius, 360, team='any', source='world'))

        source = self._neighbors if source == 'internal' else self.world.agents
        nearby = lambda pos: self.in_sight(pos, radius, alpha)

        for agent in source:

            if agent is self: continue                  # We're not in our own neighborhood

            if team != 'any' and agent.team != team:    # Filter based on the team type
                continue

            # Check if the agent's position is in sight
            if nearby(agent.relative_pos(self.pos)):
                yield agent
                continue

    def find_nearest(self, radius, alpha, team="any", except_state="foo"):
        """
        Finds the nearest point from the neighbors
        """
        nearest  = None
        distance = None
        for neighbor in self.neighbors(radius, alpha, team):
            d = self.pos.distance2(neighbor.relative_pos(self.pos))
            if (distance is None or d < distance) and neighbor.state != except_state:
                distance = d
                nearest  = neighbor
        return nearest

    ##////////////////////////////////////////////////////////////////////
    ## Movement Behavior Velocity Components
    ##////////////////////////////////////////////////////////////////////

    def cohesion(self):
        """
        Reports cohesion velocity from an array of neighbors
        """
        r = self.components['cohesion'].radius
        a = self.components['cohesion'].alpha
        neighbors = [n for n in self.neighbors(r,a, team=self.team) if (n.state != GUARDING and n.state != STUNNED)]

        if not neighbors:
            return Vector.zero()

        center = np.average(list(n.relative_pos(self.pos) for n in neighbors), axis=0)
        delta  = center - self.pos

        scale  = (delta.length / r) ** 2
        vmaxrt = VMAX * delta.unit
        return vmaxrt * scale

    def alignment(self):
        """
        Reports the alignment velocity from an array of neighbors
        """
        r = self.components['alignment'].radius
        a = self.components['alignment'].alpha
        neighbors = [x for x in list(self.neighbors(r,a, team=self.team)) if (x.state == SEEKING or x.state == SPREADING)]

        if not neighbors:
            return Vector.zero()

        center = np.average(list(n.relative_pos(self.pos) for n in neighbors), axis=0)
        deltap = center - self.pos
        scale  = deltap.length2 / (r*r)

        avgvel = np.average(list(n.vel for n in neighbors), axis=0)
        deltav = Vector.arr(avgvel)

        return VMAX * deltav.unit * scale

    def avoidance(self):
        """
        Reports the avoidance velocity from an array of agents on the opposing team.

        Changed the formula to (r - dp.length /r)
        """
        r = self.components['avoidance'].radius
        a = self.components['avoidance'].alpha

        neighbors = [x for x in list(self.neighbors(r,a, team=self.enemy)) if x.state != STUNNED]

        arr = np.zeros(2)

        for n in neighbors:
            delta = self.pos - n.relative_pos(self.pos)
            scale = (r - delta.length) / r
            arr += scale * delta.unit * VMAX

        return Vector.arr(arr)

    def separation(self):
        """
        Reports the separation velocity from an array of neighbors

        Changed the formula to (r-dp.length /r)**2
        """
        r = self.components['separation'].radius
        a = self.components['separation'].alpha
        neighbors = list(self.neighbors(r,a, team=self.team))

        if not neighbors:
            return Vector.zero()

        center = np.average(list(n.relative_pos(self.pos) for n in neighbors), axis=0)
        delta  = center - self.pos

        scale  = ((r - delta.length) / r) ** 2
        vmaxrt = VMAX * delta.unit

        return -1 * vmaxrt * scale

    def seeking(self):
        """
        Reports the seeking velocity to a target.

        How do we store a target?
        """
        if not hasattr(self, 'target') or self.target is None:
            raise Exception("In Seeking, the particle must have a target")

        direction = self.target.relative_pos(self.pos) - self.pos
        return VMAX * (direction.unit)

    def clearance(self):
        """
        Reports the clearance velocity orthogonal to current velocity
        """
        r = self.components['clearance'].radius
        a = self.components['clearance'].alpha

        neighbors = list(n for n in self.neighbors(r,a, team=self.team) if (n.state != GUARDING and n.state != STUNNED))
        if neighbors:
            center = np.average(list(n.relative_pos(self.pos) for n in neighbors), axis=0)
            delta  = center - self.pos
            if (np.cross(delta, self.vel) < 0):
                delta *= -1
            return VMAX * delta.orthogonal
        return Vector.zero()

    def homing(self):
        """
        Reports the homing velocity component to move the agent to a point
        """
        if not hasattr(self, 'target') or self.target is None:
            raise Exception("In Homing, the particle must have a target")

        direction = self.target.relative_pos(self.pos) - self.pos
        return VMAX * (direction.unit)

    def mineral_cohesion(self):
        if not hasattr(self, 'target') or self.target is None:
            raise Exception("In Mineral_Cohesion, the particle must have a target")

        direction = self.target.relative_pos(self.pos) - self.pos
        return VMAX * (direction.unit)

##########################################################################
## Resource Object
##########################################################################

class ResourceParticle(Particle):

    def __init__(self, pos, **kwargs):
        # Create the stash that the minerals contain
        self.stash = kwargs.get('stash_size', world_parameters.get('stash_size'))

        # Pass everything else back to super
        kwargs['team'] = kwargs.get('team', 'mineral')  # Add the default team
        super(ResourceParticle, self).__init__(pos, Vector.arrp(0,1), **kwargs)

    def update(self, *args, **kwargs):
        # Resources don't update!
        pass

    def blit(self, *args, **kwargs):
        # Resources don't blit!
        pass

    def mine(self):
        """
        Decrements the stash by one and returns True if there is anything
        left, otherwise returns False if this thing is unminable.
        """
        if self.stash > 0:
            self.stash -= 1
            return True
        return False

    def drop(self):
        """
        Increments the stash by one - e.g. when you're adding resources to
        a home ResourceParticle - always returns true.
        """
        self.stash += 1
        return True

    def __nonzero__(self):
        return self.stash > 0

if __name__ == '__main__':

    from params import *
    from world import SimulatedWorld

    debug = world_parameters.get('debug', True)
    world = SimulatedWorld()

    def update(iterations=1):

        def inner_update():
            for agent in world.agents:
                agent.update()
                print "%s at %s going %s" % (agent.idx, str(agent.pos), str(agent.vel))

        print "Initial state:"
        for agent in world.agents:
            print "%s at %s going %s" % (agent.idx, str(agent.pos), str(agent.vel))

        for i in xrange(1, iterations+1):
            print
            print "Iteration #%i" % i
            inner_update()

    update()
