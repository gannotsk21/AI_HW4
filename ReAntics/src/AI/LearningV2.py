# -*- coding: latin-1 -*-
from __future__ import division
import math
import pickle
import sys

sys.path.append("..")  # so other modules can be found in parent dir
from Player import *
from GameState import *
from AIPlayerUtils import *
from Inventory import *

WIN_STATE = 1.0
LOSE_STATE = -1.0
ONGOING_STATE = 0.0

DATA_FILE = "learningV2.pickle"


##
# AIPlayer
#
# Description: This AIPlayer is a Temporal Difference Learning Agent
#
# Original Authors: Jarrett Oney
#                   Sara Perkins
#
# Modified and Tweaked By: Christian Rodriguez
# TODO: Tweak and Modify as needed. Possible move design to Q Learning
# Tweaking -- Sara Perkins -- unrestrict the moves, collect inverted states
#
# Variables:
#   playerId - The id of the player.
##
class AIPlayer(Player):
    utilTable = None
    currentState = None
    currentInvState = None
    lastState = None
    lastInvState = None
    discount = .9
    learningRate = None
    epsilon = None
    depth = 2
    playerID = None
    init = True
    visitedCoords = []
    rangedNotOK = None
    testPlacement = False  # Used to test enclosed hill
    training = False  # Used to train against itself (adding new values against new bot)
    release = False  # Disables learning for release version

    # __init__
    # Description: Creates a new Player
    #
    # Parameters:
    #   inputPlayerId - The id to give the new player (int)
    #   cpy           - whether the player is a copy (when playing itself)
    ##
    def __init__(self, inputPlayerId):
        super(AIPlayer, self).__init__(inputPlayerId, "Learning Agent V2 Unrestricted")

    ##
    # getPlacement
    #
    # Description: Randomly generates a placement layout
    #
    # Parameters:
    #   currentState - The current state of the game at the time the Game is
    #       requesting a placement from the player.(GameState)
    #
    # Return: If setup phase 1: list of eleven 2-tuples of ints -> [(x1,y1), (x2,y2),,(x10,y10)]
    #       If setup phase 2: list of two 2-tuples of ints -> [(x1,y1), (x2,y2)]
    ##
    def getPlacement(self, currentState):

        # Check to see that bot works in "blocked" orientation
        # Ripped from Booger.py
        if self.testPlacement:
            self.myFood = None
            self.myTunnel = None
            self.playerID = currentState.whoseTurn
            if currentState.phase == SETUP_PHASE_1:
                return [(0, 0), (5, 1),
                        (0, 3), (1, 2), (2, 1), (3, 0),
                        (0, 2), (1, 1), (2, 0),
                        (0, 1), (1, 0)]
            elif currentState.phase == SETUP_PHASE_2:
                numToPlace = 2
                moves = []
                for i in range(0, numToPlace):
                    move = None
                    while move is None:
                        # Choose any x location
                        x = random.randint(0, 9)
                        # Choose any y location on enemy side of the board
                        y = random.randint(6, 9)
                        # Set the move if this space is empty
                        if currentState.board[x][y].constr is None and (x, y) not in moves:
                            move = (x, y)
                            # Just need to make the space non-empty. So I threw whatever I felt like in there.
                            currentState.board[x][y].constr = True
                    moves.append(move)
                return moves
            else:
                return None  # should never happen
        # Use the random placement
        else:
            numToPlace = 0
            self.playerID = currentState.whoseTurn
            # implemented by students to return their next move
            if currentState.phase == SETUP_PHASE_1:  # stuff on my side
                numToPlace = 11
                moves = []
                for i in range(0, numToPlace):
                    move = None
                    while move is None:
                        # Choose any x location
                        x = random.randint(0, 9)
                        # Choose any y location on your side of the board
                        y = random.randint(0, 3)
                        # Set the move if this space is empty
                        if currentState.board[x][y].constr is None and (x, y) not in moves:
                            move = (x, y)
                            # Just need to make the space non-empty. So I threw whatever I felt like in there.
                            currentState.board[x][y].constr = True
                    moves.append(move)
                return moves
            elif currentState.phase == SETUP_PHASE_2:  # stuff on foe's side
                numToPlace = 2
                moves = []
                for i in range(0, numToPlace):
                    move = None
                    while move is None:
                        # Choose any x location
                        x = random.randint(0, 9)
                        # Choose any y location on enemy side of the board
                        y = random.randint(6, 9)
                        # Set the move if this space is empty
                        if currentState.board[x][y].constr is None and (x, y) not in moves:
                            move = (x, y)
                            # Just need to make the space non-empty. So I threw whatever I felt like in there.
                            currentState.board[x][y].constr = True
                    moves.append(move)
                return moves
            else:
                return [(0, 0)]

    ##
    # getMove
    # Description: Gets a move. Implements Temporal Difference learning
    #
    # Parameters:
    #   currentState - The current state of the game at the time the Game is
    #       requesting a move from the player.(GameState)
    #
    # Return: Move(moveType [int], coordList [list of 2-tuples of ints], buildType [int]
    ##
    def getMove(self, currentState):
        # Initialize the utils table if first time here
        # Done here and not earlier due to CWD being in AI during init call
        if self.utilTable is None:
            self.initUtils()
            if self.init is True and self.training:  # Used to train against itself
                self.utilTable["numGames"] = 1
                self.init = False
        # Initialize epsilon and learning rate for the game
        # Set to none after each game
        if self.learningRate is None and self.epsilon is None:
            self.learningRate = self.learningFunc(self.utilTable["numGames"])
            self.epsilon = self.epsilonFunc(self.utilTable["numGames"])
        # Update the state holders
        self.lastState = self.currentState
        self.currentState = ConsolidatedState(currentState, self.playerID)
        ### update with inv
        self.lastInvState = self.currentInvState
        self.currentInvState = self.currentState.invertedConsolidatedState() #sara
        
        # Update the table if not first move
        if self.lastState is not None and not self.release:
            self.updateUtils()
            # self.dumpUtils()
        # Epsilon choice to determine move to do
        selectedMove = None
        if random.uniform(0.0, 1.0) > self.epsilon:  # Do a smart move via minimax on known values
            selectedMove = self.searchMove(currentState, 0, sys.maxsize, -sys.maxsize - 1)
        else:  # Do a random move
            possibleMoves = listAllLegalMoves(currentState)
            random.shuffle(possibleMoves)
            index = 0
            selectedMove = possibleMoves[index]
            while self.badMove(selectedMove, currentState):
                index += 1
                selectedMove = possibleMoves[index]
        return selectedMove

    ##
    # badMove
    # Description: Determines if a move is a "bad move" in a given state
    #               Bad is defined as too many ants or a worker going out of our area or the wrong type of offensive ant
    ##
    def badMove(self, selectedMove, currentState):
        # Set up needed values
        numWorkers = len(getAntList(currentState, self.playerID, (WORKER,)))
        numOffense = len(getAntList(currentState, self.playerID, (DRONE, SOLDIER, R_SOLDIER,)))
        offensiveTypes = (DRONE, SOLDIER, R_SOLDIER)
        badOffensiveTypes = (DRONE, SOLDIER)
        # Check if we have too many ants
        cappedAnts = (selectedMove.moveType == BUILD and ((selectedMove.buildType is WORKER and numWorkers >= 3) or (
                selectedMove.buildType in offensiveTypes and numOffense >= 2)))
        # Check if a worker is leaving our territory
        OOBWorker = (selectedMove.moveType == MOVE_ANT and getAntAt(currentState, selectedMove.coordList[
            0]).type is WORKER and not isPathOkForQueen(selectedMove.coordList))
        # Only do ranged ants
        rangedOnly = selectedMove.moveType == BUILD and selectedMove.buildType in badOffensiveTypes
        # Only do ranged ants if there is a clear path from the anthill
        rangedAllowed = selectedMove.moveType == BUILD and selectedMove.buildType is R_SOLDIER and self.rangedNotOK

        # unrestrict -- determine that all moves are good
        return False #cappedAnts or OOBWorker or rangedOnly or rangedAllowed

    ##
    # getAttack
    # Description: Chooses somebody to attack, if possible. Simply chooses one randomly.
    #
    # Parameters:
    #   currentState - The current state of the game at the time the Game is requesting
    #       a move from the player. (GameState)
    #   attackingAnt - A clone of the ant currently making the attack. (Ant)
    #   enemyLocation - A list of coordinate locations for valid attacks (i.e.
    #       enemies within range) ([list of 2-tuples of ints])
    #
    # Return: A coordinate that matches one of the entries of enemyLocations. ((int,int))
    ##
    def getAttack(self, currentState, attackingAnt, enemyLocations):
        return enemyLocations[random.randint(0, len(enemyLocations) - 1)]

    ##
    # registerWin
    # Description: Updates the previous state given a win or loss
    #
    # Parameters:
    #   hasWon - True if the player has won the game, False if the player lost. (Boolean)
    ##
    def registerWin(self, hasWon):
        # Update the last state seen before we won
        self.lastState = self.currentState
        self.lastInvState = self.currentInvState
        # Update the util table and num games
        if not self.release:
            self.updateUtils(True, hasWon)
            self.utilTable["numGames"] += 1
            self.dumpUtils()
        # Reset variables so no "holding over" on variables for next game
        self.currentState = None
        self.lastState = None
        # Reset rates to none to recalculate
        self.learningRate = None
        self.epsilon = None
##        self.rangedNotOK = None
        self.visitedCoords = []
        pass

    ##
    # initUtils
    # Description: Initializes the utility table
    #
    # The utils file needs to be in the same folder as Game.py
    ##
    def initUtils(self):
        try:
            file = open(DATA_FILE, "rb")
            self.utilTable = pickle.load(file)
            # print "Read the file"
        except IOError:  # no file yet
            self.utilTable = dict()
            self.utilTable["numGames"] = 1
            if self.release:
                print("WARNING: Could not read the file and in release mode")
                print("Release mode needs the file to run properly")
                print("Ensure that the file is in the same folder as Game.py")
                sys.exit(0)
            # print "Made the table"

    ##
    # dumpUtils
    # Description: Dumps the util table to a file
    ##
    def dumpUtils(self):
        file = open(DATA_FILE, "wb")
        pickle.dump(self.utilTable, file)
        file.close()
        # print "Util Table has " + str(len(self.utilTable)) + " entries"

    ##
    # updateUtils
    # Description: Updates the utility value for the last state seen
    #
    # Parameters:
    #   endGame - True if the game has ended
    #   hasWon - True if the AI has won
    ##
    def updateUtils(self, endGame=False, hasWon=False):

        ## regular
        # Set the reward
        reward = -.01
        # Set the "next state" val
        currentStateVal = None
        if endGame:  # end game condition, return the reward
            if hasWon:
                currentStateVal = 1.0
            else:
                currentStateVal = -1.0
        elif self.currentState in self.utilTable:  # not end game, seen state before
            currentStateVal = self.utilTable[self.currentState]
        else:  # not end game, new state
            currentStateVal = 0.0
        # Update the table
        oldVal = 0.0
        if self.lastState in self.utilTable:  # state has been seen before
            oldVal = self.utilTable[self.lastState]

        # Updates the value in the utils table
        self.utilTable[self.lastState] = oldVal + self.learningRate * (
                reward + self.discount * currentStateVal - oldVal)


        ## repeat for the inverted state
        # Set the reward
        reward = -.01
        # Set the "next state" val
        currentInvStateVal = None
        if endGame:  # end game condition, return the reward
            if hasWon:
                currentInvStateVal = 1.0
            else:
                currentInvStateVal = -1.0
        elif self.currentInvState in self.utilTable:  # not end game, seen state before
            currentInvStateVal = self.utilTable[self.currentInvState]
        else:  # not end game, new state
            currentInvStateVal = 0.0
        # Update the table
        oldVal = 0.0
        if self.lastInvState in self.utilTable:  # state has been seen before
            oldVal = self.utilTable[self.lastInvState]

        # Updates the value in the utils table
        self.utilTable[self.lastInvState] = oldVal + self.learningRate * (
                reward + self.discount * currentInvStateVal - oldVal)

    ##
    # learningRate
    # Description: Outputs a value between 1.0 and 0.0 dependant on how many games have been played
    #
    # Parameters:
    #       numGames - The amount of games played
    #
    # Return:
    #       The learning rate, a float between 0.0 and 1.0
    ##
    def learningFunc(self, numGames):
        if self.release:
            return 0.0
            # Starts at 1.0, hits .5 at 42 games, hits .25 at 73
        val = 2 / (math.exp(numGames / 75) + 1)
        # print "learning rate is " + str(val)
        return val

    ##
    # epsilon
    # Desription: Outputs a value between 1.0 and 0.0 dependant on how many games have been played
    #
    # Parameters:
    #       numGames - The amount of games played
    #
    # Return:
    #       The epsilon rate, a float between 0.0 and 1.0
    ##
    def epsilonFunc(self, numGames):
        if self.release:
            return -1.0
        # Using the same as the learning rate, only slower to get to less value more slowly
        val = 2 / (math.exp(numGames / 150) + 1)
        # print "epsilon is " + str(val)
        return val

    ##
    # winState
    # Description: Scans a state and says whether or not the AI would win/lose
    #
    # Paramters:
    #   - The state to be scanned
    #
    # Return:
    #   - An float constant relating to whether the AI would win, lose, or neither
    ##
    def winState(self, theState):
        ids = [1 - self.playerID, self.playerID]
        win = []
        # Check all the win conditions
        for ID in ids:
            if theState.inventories[ids[1 - ID]].getQueen() is None or theState.inventories[
                ids[1 - ID]].getAnthill().captureHealth is 0 or theState.inventories[
                ids[ID]].foodCount >= FOOD_GOAL or (theState.inventories[ids[1 - ID]].foodCount is 0 and len(
                    theState.inventories[ids[1 - ID]].ants) is 1):
                win.append(True)
            else:
                win.append(False)
        # Check if a player won
        if win[0]:
            return LOSE_STATE
        elif win[1]:
            return WIN_STATE
        else:
            return ONGOING_STATE

##    ##
##    # findRangedPath
##    # Description: Recursively finds if there is a path for a ranged ant
##    #
##    # Parameters:
##    #   - The state of the game
##    #
##    # Return:
##    #   - Boolean if there is a path available
##    ##
##    def findRangedPath(self, theState, origCoord):
##        copyState = self.fastclone(theState)
##        adjCoords = listReachableAdjacent(copyState, origCoord, 1)
##        # print origCoord
##        # print adjCoords
##        for coord in adjCoords:
##            if coord[1] >= 4:
##                return True
##            if coord in self.visitedCoords:
##                continue
##            else:
##                self.visitedCoords.append(coord)
##                if self.findRangedPath(copyState, coord):
##                    return True
##        return False

    ##
    # fastclone
    #
    # Description: Returns a deep copy of itself *without* a board (which is set
    # to None).  Omitting the board makes the clone run much faster and, if
    # necessary, the board can be reconstructed from the inventories.
    #
    # Ripped from gamestate, adjusted to not copy ants
    #
    # Return: a GameState object _almost_ identical to the original
    ##
    def fastclone(self, theState):
        newBoard = None
        # For speed, preallocate the lists at their eventual size
        ants1 = []
        ants2 = []
        cons1 = [None] * len(theState.inventories[PLAYER_ONE].constrs)
        cons2 = [None] * len(theState.inventories[PLAYER_TWO].constrs)
        cons3 = [None] * len(theState.inventories[NEUTRAL].constrs)
        antIndex1 = 0
        antIndex2 = 0
        conIndex1 = 0
        conIndex2 = 0
        conIndex3 = 0
        # clone all the entries in the inventories
        # deleted the fillers for the ants
        for constr in theState.inventories[PLAYER_ONE].constrs:
            cons1[conIndex1] = constr.clone()
            conIndex1 += 1
        for constr in theState.inventories[PLAYER_TWO].constrs:
            cons2[conIndex2] = constr.clone()
            conIndex2 += 1
        for constr in theState.inventories[NEUTRAL].constrs:
            cons3[conIndex3] = constr.clone()
            conIndex3 += 1
        # clone the list of inventory objects
        food1 = theState.inventories[PLAYER_ONE].foodCount
        food2 = theState.inventories[PLAYER_TWO].foodCount
        newInventories = [Inventory(PLAYER_ONE, ants1, cons1, food1),
                          Inventory(PLAYER_TWO, ants2, cons2, food2),
                          Inventory(NEUTRAL, [], cons3, 0)]
        return GameState(newBoard, newInventories, theState.phase, theState.whoseTurn)

    #######################################
    # MINIMAX CODE
    #######################################
    ##
    # bestScore
    # Description: Determines the best/worst score in the list, gives the best move if depth = 0
    #
    # Parameters:
    #   listOfNodes -   The nodes correlating to a given states possible moves
    #   depthLevel -    The current depth level of the search
    #   player -        The current player who is making the turn, detemines best/worst
    #
    # Return: The Move to be made if depthLevel is 0, the best/worst score in the list otherwise
    ##
    def bestScore(self, listOfNodes, depthLevel, player):
        score = None
        # If depthLevel is 0, then we need to return the best move
        # At level zero, is necessarily my turn so pick the best
        if depthLevel == 0:
            # if multiple "equal" moves, pick one at random
            bestList = []
            for node in listOfNodes:
                if self.winState(node["State"]) is WIN_STATE and node["Move"].moveType is not END:
                    return node["Move"]
                elif score is None:
                    score = node["Score"]
                    bestList.append(node)
                elif node["Score"] > score:
                    score = node["Score"]
                    del bestList[:]
                    bestList.append(node)
                elif node["Score"] == score:
                    bestList.append(node)
            # print self.totalEval
            try:
                return random.choice(bestList)["Move"]
            except IndexError:
                return Move(END, None, None)
        # If depth level is over 0, then return the best/worst score of the set
        # Due to alpha/beta pruning, should not reach this portion of code now
        # Best
        elif player == self.playerID:
            bestScore = -sys.maxsize - 1
            for node in listOfNodes:
                if bestScore < node["Score"]:
                    bestScore = node["Score"]
            return bestScore
        # Worst, player must not be me
        else:
            worstScore = sys.maxsize
            for node in listOfNodes:
                if worstScore > node["Score"]:
                    worstScore = node["Score"]
            return worstScore

    ##
    # searchMove
    # Description:   Recursively searches for the best move by analyzing the gameStates
    #               that result from a given move
    #
    # Parameters:
    #   currentState -  The state of the game (GameState)
    #   depthLevel -    The current depth of the search
    #   alpha -         The alpha boundary
    #   beta -          The beta boundary
    #
    # Return:
    #   The Move to be made
    #   The "score" of a subtree
    ##
    def searchMove(self, currentState, depthLevel, alpha, beta):
        ### should add inverse state using
        state = ConsolidatedState(currentState, self.playerID) # inv
        # We are going no lower
        if depthLevel == self.depth:
            if state in self.utilTable:
                return self.utilTable[state]
            else:
                return 0.0
        moves = listAllLegalMoves(currentState)
        initScore = 0.0
        if state in self.utilTable:
            initScore = self.utilTable[state]
        nodes = []
        numWorkers = len(getAntList(currentState, self.playerID, (WORKER,)))
        numOffense = len(getAntList(currentState, self.playerID, (DRONE, SOLDIER, R_SOLDIER,)))
        offensiveTypes = (DRONE, SOLDIER, R_SOLDIER)
        for move in moves:
            if self.badMove(move, currentState):
                continue
            newState = getNextStateAdversarial(currentState, move)
            # inv not needed, just search from cur
            newConsolidatedState = ConsolidatedState(newState, self.playerID) 
            # Get evaluations based on utils table
            newScore = 0.0
            if newConsolidatedState in self.utilTable:
                newScore = self.utilTable[newConsolidatedState]
            else:
                newScore = self.winState(currentState)
            nodes.append(
                {"Move": move, "State": newState, "Score": self.searchMove(newState, depthLevel + 1, alpha, beta)})
        # Sort the nodes depending on who's turn
        if currentState.whoseTurn == self.playerID:
            nodes.sort(key=lambda node: node["Score"], reverse=True)
        else:
            nodes.sort(key=lambda node: node["Score"], reverse=False)
        # Only take the top fifth of nodes if more than 10
        if len(nodes) > 10:
            index = int(math.floor(len(nodes) / 5))
            nodes = nodes[:index]
        # MAX
        # Expand the existing nodes
        if currentState.whoseTurn == self.playerID and depthLevel > 0:
            score = -sys.maxsize - 1
            for node in nodes:
                score = max(score, node["Score"])
                alpha = max(score, alpha)
                # Check to see if alpha >= beta; return beta if is not depth 0 and have changed beta
                if alpha >= beta:
                    return score
        # MIN
        if currentState.whoseTurn != self.playerID and depthLevel > 0:
            score = sys.maxsize
            for node in nodes:
                score = min(score, node["Score"])
                beta = min(score, beta)
                # Check to see if alpha >= beta; return beta if is not depth 0 and have changed beta
                if alpha >= beta:
                    return score
        # Will return a value if depth over 1, move if depth = 0
        # Should not get to this point when depth is greater than 1 due to pruning
        return self.bestScore(nodes, depthLevel, currentState.whoseTurn)


##
# ConsolidatedState
#
# Represents a cosolidated state of the game
##
class ConsolidatedState:
    ##
    # init
    # Description: Creates the object for the consolidated state and
    #               fills in the instance variables
    #
    # Parameters:
    #   - The GameState to be consolidated
    #   - The player's ID (integer)
    ##
    def __init__(self, theState = None, playerID = None):

        # to be used for the inverted state
        if theState is None and playerID is None:
            return

        # normal consolidated state creation
        myInv = None
        enemyInv = None
        for inv in theState.inventories:
            if inv.player == playerID:
                myInv = inv
            elif inv.player == 1 - playerID:
                enemyInv = inv
        # queen health
        self.myHealth = 0
        if myInv.getQueen() is not None:
            self.myHealth = myInv.getQueen().health
        self.theirHealth = 0
        if enemyInv.getQueen() is not None:
            self.theirHealth = enemyInv.getQueen().health
        # amt worker ants
        self.myWorkerAmt = len(getAntList(theState, playerID, (WORKER,)))
        self.theirWorkerAmt = len(getAntList(theState, 1 - playerID, (WORKER,)))
        # amt offensive ants
        self.myOffenseAmt = len(getAntList(theState, playerID, (DRONE, SOLDIER, R_SOLDIER,)))
        self.theirOffenseAmt = len(getAntList(theState, 1 - playerID, (DRONE, SOLDIER, R_SOLDIER,)))
        # amt of food
        self.myFood = myInv.foodCount
        self.theirFood = enemyInv.foodCount
        # amt of food being caried by ants
        myWorkers = getAntList(theState, playerID, (WORKER,))
        foodAmount = 0
        for ant in myWorkers:
            if ant.carrying:
                foodAmount += 1
        self.myCarriedFood = foodAmount
        theirWorkers = getAntList(theState, 1 - playerID, (WORKER,))
        theirFoodAmount = 0
        for ant in myWorkers:
            if ant.carrying:
                theirFoodAmount += 1
        self.theirCarriedFood = theirFoodAmount
        # capture health for anthill
        self.myAnthillHealth = myInv.getAnthill().captureHealth
        self.theirAnthillHealth = enemyInv.getAnthill().captureHealth
        # dist to target
        myBases = getConstrList(theState, playerID, (TUNNEL, ANTHILL,))
        theirBases = getConstrList(theState, 1 - playerID, (TUNNEL, ANTHILL,))
        foods = []
        for food in getConstrList(theState, None, (FOOD,)):
            foods.append(food)
        distances = []
        for worker in myWorkers:
            dist = 999
            if worker.carrying:
                for cache in myBases:
                    temp = approxDist(worker.coords, cache.coords)
                    if temp < dist:
                        dist = temp
            else:
                for food in foods:
                    temp = approxDist(worker.coords, food.coords)
                    if temp < dist:
                        dist = temp
            distances.append(dist)
        self.myWorkerDist = None
        if len(distances) > 0:
            self.myWorkerDist = min(distances)
        else:
            self.myWorkerDist = 999
        distances = []
        for worker in theirWorkers:
            dist = 999
            if worker.carrying:
                for cache in theirBases:
                    temp = approxDist(worker.coords, cache.coords)
                    if temp < dist:
                        dist = temp
            else:
                for food in foods:
                    temp = approxDist(worker.coords, food.coords)
                    if temp < dist:
                        dist = temp
            distances.append(dist)
        self.theirWorkerDist = None
        if len(distances) > 0:
            self.theirWorkerDist = min(distances)
        else:
            self.theirWorkerDist = 999
        # dist for offensive ants
        myOffense = getAntList(theState, playerID, (DRONE, SOLDIER, R_SOLDIER,))
        theirOffense = getAntList(theState, 1 - playerID, (DRONE, SOLDIER, R_SOLDIER,))
        distances = []
        for ant in myOffense:
            dist = 999
            for enemy in theirWorkers:
                temp = approxDist(ant.coords, enemy.coords)
                if temp < dist:
                    dist = temp
            distances.append(dist)
        self.myOffenseDist = None
        if len(distances) > 0:
            self.myOffenseDist = min(distances)
        else:
            self.myOffenseDist = 999
        distances = []
        for ant in theirOffense:
            dist = 999
            for enemy in myWorkers:
                temp = approxDist(ant.coords, enemy.coords)
                if temp < dist:
                    dist = temp
            distances.append(dist)
        self.theirOffenseDist = None
        if len(distances) > 0:
            self.theirOffenseDist = min(distances)
        else:
            self.theirOffenseDist = 999

    ##
    # Equals function
    # Description: Determines if two states are semantically the same
    #
    # Parameter:
    #   - The ConsolidatedState to be compared
    #
    # Returns:
    #   - Boolean, whether or not the states are the same
    ##
    def __eq__(self, other):
        match = True
        match = match and self.theirHealth == other.theirHealth
        match = match and self.myOffenseAmt == other.myOffenseAmt
        match = match and self.myHealth == other.myHealth
        match = match and self.myWorkerAmt == other.myWorkerAmt
        match = match and self.theirAnthillHealth == other.theirAnthillHealth
        match = match and self.theirOffenseAmt == other.theirOffenseAmt
        match = match and self.theirCarriedFood == other.theirCarriedFood
        match = match and self.myWorkerDist == other.myWorkerDist
        match = match and self.myOffenseDist == other.myOffenseDist
        match = match and self.myAnthillHealth == other.myAnthillHealth
        match = match and self.theirWorkerAmt == other.theirWorkerAmt
        match = match and self.theirFood == other.theirFood
        match = match and self.myFood == other.myFood
        match = match and self.myCarriedFood == other.myCarriedFood
        match = match and self.theirOffenseDist == other.theirOffenseDist
        match = match and self.theirWorkerDist == other.theirWorkerDist
        return match

    ##
    # Hash function
    # Description: THe hash function for the object
    # Used to enable dictionary key usage properly
    ##
    def __hash__(self):
        return hash((self.theirHealth, self.myOffenseAmt, self.myHealth, self.myWorkerAmt, self.theirAnthillHealth,
                     self.theirOffenseAmt, self.theirCarriedFood, self.myWorkerDist, self.myOffenseDist,
                     self.myAnthillHealth, self.theirWorkerAmt, self.theirFood, self.myFood, self.myCarriedFood,
                     self.theirOffenseDist, self.theirWorkerDist))

    ###
    # create an inverse state
    def invertedConsolidatedState ( self ) :
        inv = ConsolidatedState()
        
        inv.myOffenseAmt       = self.theirOffenseAmt
        inv.myHealth           = self.theirHealth
        inv.myWorkerAmt        = self.theirWorkerAmt
        inv.myWorkerDist       = self.theirWorkerDist
        inv.myOffenseDist      = self.theirOffenseDist
        inv.myAnthillHealth    = self.theirAnthillHealth
        inv.myFood             = self.theirFood
        inv.myCarriedFood      = self.theirCarriedFood
        
        inv.theirOffenseDist   = self.myOffenseDist
        inv.theirWorkerDist    = self.myWorkerDist
        inv.theirHealth        = self.myHealth
        inv.theirAnthillHealth = self.myAnthillHealth
        inv.theirOffenseAmt    = self.myOffenseAmt
        inv.theirCarriedFood   = self.myCarriedFood
        inv.theirWorkerAmt     = self.myWorkerAmt
        inv.theirFood          = self.myFood

        return inv

