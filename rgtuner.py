#!/usr/bin/env python2
from __future__ import print_function
import os
import multiprocessing
import re
import shutil
import argparse
filesRemaining = []
botScores = {}
import random
from rgkit.run import Runner, Options
from rgkit.settings import settings as default_settings

def make_variants(variable, robot_file, possibilities):
    """Makes variants of the file robot_file  with the constant variable
    changed for each possibility.

    e.g. if the variable is "ELEPHANTS" and the possibilities are [1, 2, 3],
    this will find the line
    ELEPHANTS = 3
    in robobt_file and make a copy of the file for each value in possibilities.
    1.py will have ELEPHANTS = 1, 2.py will have ELEPHANTS = 2, etc.

    Raises IndexError if the variable name is not found in the file robot_file.
    The line assigning the constant variable must be the first line in that
    file has the variable name in it.
    """
    filenames = []
    with open(robot_file, 'r') as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
      if variable in line:
          break
    else:
      raise IndexError('variable name %s is not found in file %s' % (variable, robot_file))
    assert '=' in line
    for p in possibilities:
        varandp = variable + str(p)
        lines[i] = "%s = %s\n" % (variable, p)
        filenames.append(varandp)
        with open(varandp, 'w') as pfile:
            for line in lines:
                pfile.write(line)
    return filenames


def get_current_value(variable, robot_file):
    """
    Returns the value of the constant variable in the robot file.

    This function finds the first line in the file robot_file that has the
    variable name in it, and parses the value after the '=' in that line for a
    float, returning it.

    Raises IndexError if the variable name is not found in the file robot_file.
    The line assigning the constant variable must be the first line in that
    file has the variable name in it.
    """
    with open(robot_file, 'r') as f:
        for line in f:
          if variable in line:
            break
        else:
          raise IndexError('variable name %s is not found in file %s' % (variable, robot_file))
    assert '=' in line
    return float(line[line.index('=') + 1:])


def optimize_variable(precision, matchNum, enemies, variable, robot_file, processes):
    pool = multiprocessing.Pool(processes)
    """
    Creates a bunch of variants of the file robot_file, each with variable
    changed, then runs a tournament between the variants to find the best one.
    The file robot_fily is modified to contain the best value, and it is
    returned.
    """
    try:
      base_value = get_current_value(variable, robot_file)
      while precision >= 0.1:
          print('RUNNING WITH BASE VALUE', base_value, \
                'PRECISION', precision)

          values_to_test = [base_value - precision,
            base_value + precision, base_value]

          files = make_variants(variable, robot_file, values_to_test)
          best_file = run_tourney(matchNum,enemies, files, pool)
          best_value = values_to_test[files.index(best_file)]
          if best_value == base_value:
              precision /= 2.0
              print('best value remains', best_value)
              print('decreasing precision to', precision)
          else:
              base_value = best_value
              print('new \'best\' value is', best_value)

      shutil.copy(make_variants(variable, robot_file, [base_value])[0],
                robot_file)
    #make double sure we close processes so as to not make a process bomb when testing
    except KeyboardInterrupt:
        print("terminating pool, please wait...")
        pool.terminate()
        raise
    #close processes explicitly insead of relying on GC to do it
    pool.close()
    pool.join()
    return base_value

def run_match(args):
    #rgkit integration
    try:
      bot1, bot2, n_matches = args
      res = Runner(player_files=(bot1,bot2), options=Options(n_of_games=n_matches, quiet=4, game_seed=random.randint(0, default_settings.max_seed))).run()
      dif = 0
      for scores0, scores1 in res:
        dif += scores0 - scores1
      return dif
    #if there is an error, return immediatly so that the program can quit
    except KeyboardInterrupt:
      pass


def versus(matches_to_run, bot1, bot2, pool):
    """Launches a multithreaded comparison between two robot files.
    run_match() is run in separate processes, one for each CPU core by default, until 100
    matches (default) are run. returns bot1 score - bot2 score"""
    try:
      #find out pool size
      psize = len(pool._pool)
      rem, mod = divmod(matches_to_run, psize)
      matchnums = []
      #create list that lists how many matches to run and which bots to run them with
      for _ in xrange(psize):
        if mod:
          mod -= 1
          matchnums.append((bot1, bot2, rem+1))
        else:
          matchnums.append((bot1,bot2, rem))
      #sum up all the partial differences returned by the pool
      #using imap on the list created earlier
      return sum(pool.imap_unordered(run_match, matchnums))
    except KeyboardInterrupt:
        print('user did ctrl+c, ABORT EVERYTHING\n Removing files...')
        for bot in filesRemaining:
            os.remove(bot)
        raise KeyboardInterrupt()

def run_tourney(matchNum,enemies, botfiles, pool):
    """Runs a tournament between all bot files in botfiles.
    Returns the winner of the tournament."""
    bestWin = ['', -5000]
    scores = {}
    for bot1 in botfiles:
        filesRemaining.append(bot1)
        scores[bot1] = 0
    for enemy in enemies:
        for bot1 in botfiles:
            if bot1 in botScores[enemy] and botScores[enemy][bot1] != 0:
                winScore = botScores[enemy][bot1]
                print('ALREADY SCORED',str(bot1))
            else:
                winScore = versus(matchNum,bot1, enemy, pool)
                botScores[enemy][bot1] = winScore
            while winScore == 0:
                print('VERSUS WAS A TIE. RETRYING...')
                winScore = versus(matchNum,bot1, enemy, pool)
                print('Difference in score:',str(bestWin[1]))
            scores[bot1] += winScore
        print(scores)
    for bot1 in botfiles:
        for bot2 in botfiles:
            if bot1 != bot2 and scores[bot1] == scores[bot2]:
                print("Two bots have same score, finding the winner")
                bestWin[1] = versus(matchNum,bot1, bot2, pool)
                while bestWin[1] == 0:
                    print("Wow. Another Tie.")
                    bestWin[1] = versus(matchNum,bot1, bot2, pool)
                if bestWin[1] < 0:
                    bestWin[0] = bot2
                elif bestWin[1] > 0:
                    bestWin[0] = bot1
                else:
                    print("WTF? Impossible Tie.")
            elif scores[bot1] > bestWin[1]:
                bestWin[1] = scores[bot1]
                bestWin[0] = bot1

    bestwin = bestWin[0]
    for bf in botfiles:
        if not bf == bestwin:
            print('removing',bf)
            os.remove(bf)
            filesRemaining.remove(bf)
    print('Best Score:',str(bestWin[1]))
    return bestwin


def main():

    parser = argparse.ArgumentParser(
        description="Optimize constant values for robotgame.")
    parser.add_argument(
        "constant", type=str, help='The constant name to optimize.')
    parser.add_argument(
        "file", type=str, help='The file of the robot to optimize.')
    parser.add_argument(
        "enemies", type=str, help='A comma-separated list of the enemy files.')
    parser.add_argument(
        "-pr", "--precision",
        default=8.0,
        type=float, help='The precision to start adjusting values at')
    parser.add_argument(
        "-m", "--matches",
        default=100,
        type=int, help='The number of matches to run per tourney')
    parser.add_argument(
        "-p", "--processes",
        default=multiprocessing.cpu_count(),
        type=int, help='The number of processes to simulate in')
    args = vars(parser.parse_args())
    eList = args['enemies'].split(',')
    for e in eList:
        botScores[e] = {}
    best_value = optimize_variable(args['precision'],args['matches'],eList,
        args['constant'], args['file'], processes=args['processes'])
    print(best_value)


if __name__ == '__main__':
    main()
