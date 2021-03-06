#!/usr/bin/env python

# runsim
# Runs the swarm simulation
#
# Author:   Benjamin Bengfort <bengfort@cs.umd.edu>
# Created:  Thu Feb 27 17:10:23 2014 -0500
#
# Copyright (C) 2014 UMD Metacognitive Lab
# For license information, see LICENSE.txt
#
# ID: swarmsim.py [] bengfort@cs.umd.edu $

"""
Run the swarm simulation.
"""

##########################################################################
## Imports
##########################################################################

import os
import sys
import csv
import time
import argparse
import cProfile

from swarm import World
from swarm import visualize
from swarm.exceptions import SimulationException

##########################################################################
## Command Line Variables
##########################################################################

DESCRIPTION = "Run the multi-agent swarm simulation."
EPILOG      = "(C) Copyright University of Maryland 2014"
VERSION     = "1.3"

##########################################################################
## Commands
##########################################################################

def visual(args):
    """
    Run the visual/PyGame version of the simulation
    """
    start = time.time()
    world = World(ally_conf_path=args.conf_path)
    size  = args.screen_size
    fps   = args.fps
    visualize(world, [size, size], fps)
    finit = time.time()
    delta = finit - start

    output = []
    output.append("Ran %i time steps in %0.3f seconds" % (world.time, delta))
    output.append("Agents successfully collected %i resources" % world.ally_home.stash)
    return "\n".join(output)

def simulate(args):
    """
    Run a headless simulation with configuration file
    """
    start = time.time()
    world = World(ally_conf_path=args.conf_path)

    print "Starting headless simulation, use CTRL+C to quit."
    while world.time < world.iterations:
        try:
            world.update()
            if world.time % 1000 == 0:
                print "%ik iterations completed" % (world.time / 1000)
        except KeyboardInterrupt:
            print "Quitting Early!"
            break

    finit = time.time()
    delta = finit - start

    output = []
    output.append("Ran %i time steps in %0.3f seconds" % (world.time, delta))
    output.append("Agents successfully collected %i resources" % world.ally_home.stash)
    return "\n".join(output)

def profile(args):
    """
    Use cProfile to audit 100 timesteps of the simulation
    """

    def run():
        world = World(ally_conf_path=args.conf_path)
        while world.time < args.iterations:
            try:
                world.update()
            except KeyboardInterrupt:
                break

    print "Starting profiling for %i timesteps, use CTRL+C to quit." % args.iterations
    cProfile.runctx('run()', globals(), locals(), args.filename, args.sort)
    return ''

def head2head(args):
    """
    Run a head to head simulation, outputing the magnitude of the stash of
    each team in the simulation at every time step.
    """
    start = time.time()
    world = World(ally_conf_path=args.conf_path, maximum_time=args.iterations)

    print "Starting headless simulation, use CTRL+C to quit."
    writer = csv.writer(args.stream, delimiter='\t')
    writer.writerow(('black', 'red'))
    while world.time < world.iterations:
        try:
            world.update()
            writer.writerow((str(world.ally_home.stash), str(world.enemy_home.stash)))
            if world.time % 1000 == 0:
                print "%ik iterations completed" % (world.time / 1000)
        except KeyboardInterrupt:
            print "Quitting Early!"
            break

    finit = time.time()
    delta = finit - start

    output = []
    output.append("Ran %i time steps in %0.3f seconds" % (world.time, delta))
    output.append("Agents successfully collected %i resources" % world.ally_home.stash)
    return "\n".join(output)

##########################################################################
## Main method
##########################################################################

def main(*argv):

    # Construct the argument parser
    parser = argparse.ArgumentParser(description=DESCRIPTION, epilog=EPILOG, version=VERSION)
    subparsers = parser.add_subparsers(title='commands', description='Administrative commands for simulations')

    # parser for visual simulation
    visual_parser = subparsers.add_parser('visual', help='Run the visual/PyGame version of the simulation')
    visual_parser.add_argument('-s', '--screen-size', metavar='SIZE', type=int, dest='screen_size',
                               default=720, help='size of window to run in.')
    visual_parser.add_argument('-f', '--fps', type=int, default=30, help='frames per second to run simulation in.')
    visual_parser.add_argument('-c', '--conf-path', type=str, dest='conf_path', default='./conf/params.yaml', help='path to ally configuration file.')
    visual_parser.set_defaults(func=visual)

    # parser headless simulation
    headless_parser = subparsers.add_parser('simulate', help='Run a headless simulation with the configuration file')
    headless_parser.add_argument('-c', '--conf-path', type=str, dest='conf_path', default='./conf/params.yaml', help='path to ally configuration file.')
    headless_parser.set_defaults(func=simulate)

    # parser for profiling
    profile_parser = subparsers.add_parser('profile', help='Use cProfile to audit 100 timesteps of the simulation')
    profile_parser.add_argument('-f', '--filename', metavar='PATH', type=str, default=None,
                                help='Filename to write the stats out to.')
    profile_parser.add_argument('-s', '--sort', choices=('calls', 'cumulative', 'name', 'time'),
                                default=-1, help='Sort the statistics on a particular field.')
    profile_parser.add_argument('-i', '--iterations', metavar='STEPS', type=int, default=100,
                                help='Number of iterations to profile')
    profile_parser.add_argument('-c', '--conf-path', type=str, dest='conf_path', default='./conf/params.yaml', help='path to ally configuration file.')
    profile_parser.set_defaults(func=profile)

    # head2head headless simulation
    head2head_parser = subparsers.add_parser('head2head', help='Run a headless simulation with the configuration file')
    head2head_parser.add_argument('-c', '--conf-path', type=str, dest='conf_path', default='./conf/params.yaml', help='path to ally configuration file.')
    head2head_parser.add_argument('-o', '--outpath', dest='stream', type=argparse.FileType('w'), default=sys.stdout, help='Write head to head results out.')
    head2head_parser.add_argument('-i', '--iterations', metavar='STEPS', type=int, default=10000,
                                    help='Number of iterations to profile')
    head2head_parser.set_defaults(func=head2head)

    # Handle input from the command line
    args = parser.parse_args()            # Parse the arguments
    try:
        msg = args.func(args)             # Call the default function
        parser.exit(0, msg+"\n")          # Exit clearnly with message
    except SimulationException as e:
        parser.error(str(e)+"\n")          # Exit with error

if __name__ == '__main__':
    main(*sys.argv)
