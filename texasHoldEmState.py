from copy import deepcopy

from mcts import mcts

from honest_player import HonestPlayer
from pypokerengine.api.emulator import Emulator
from pypokerengine.engine.game_evaluator import GameEvaluator
from pypokerengine.engine.poker_constants import PokerConstants as Const
from pypokerengine.players import BasePokerPlayer
from pypokerengine.utils.card_utils import gen_cards
from pypokerengine.utils.game_state_utils import (attach_hole_card,
                                                  attach_hole_card_from_deck,
                                                  deepcopy_game_state,
                                                  restore_game_state)
from pypokerengine.utils.visualize_utils import visualize_round_state
from RandomPlayer import RandomPlayer


class TexasHoldemState():
    """
    Create a TexasHoldemState for each game state. These serve as the states
    for the MCTS
    """
    def __init__(self, valid_action, hole_card, game_state, emulator):
        self.valid_action = valid_action
        self.hole_card = hole_card
        self.game_state = deepcopy_game_state(game_state)
        self.emulator = emulator

    def getCurrentPlayer(self):
        return not self.round_state["next_player"]

    def getPossibleActions(self):
        act_list = []
        for i in self.valid_action:
            act_list.append(i["action"])
        return act_list

    def takeAction(self, action):
        """
        We make use of Emulator to get our next state
        """
        new_game_state, events = self.emulator.apply_action(self.game_state, action)
        newState = deepcopy(self)
        newState.game_state = new_game_state
        return newState

    def isTerminal(self):
        return self.game_state["street"] == Const.Street.FINISHED

    def getReward(self):
        return self.game_state["table"].serialize()[1][0][2] > 10000


class RLPLayer(BasePokerPlayer):

    # Setup Emulator object by registering game information
    def receive_game_start_message(self, game_info):
        # Set up Game
        player_num = game_info["player_num"]
        max_round = game_info["rule"]["max_round"]
        small_blind_amount = game_info["rule"]["small_blind_amount"]
        ante_amount = game_info["rule"]["ante"]
        blind_structure = game_info["rule"]["blind_structure"]

        # Set up Emulator
        self.emulator = Emulator()
        self.emulator.set_game_rule(player_num, max_round, small_blind_amount, ante_amount)
        self.emulator.set_blind_structure(blind_structure)

        self.uuid = game_info["seats"][0]["uuid"]
        
        # Register algorithm of each player which used in the simulation.
        for player_info in game_info["seats"]:
            self.emulator.register_player(player_info["uuid"], RandomPlayer())

        # self.game_state = self.emulator.start_new_round(self.game_state)

    def declare_action(self, valid_actions, hole_card, round_state):
        # Set up new game_state with hole cards
        game_state = deepcopy_game_state(self._setup_game_state(round_state, hole_card))
        # visualize_round_state(round_state)
        # Decide action by using MCTS
        searcher = mcts(timeLimit=90)
        init_state = TexasHoldemState(valid_actions, hole_card, game_state, self.emulator)
        bestAction = searcher.search(initialState=init_state)
        # updated_state, events = self.emulator.apply_action(game_state, "fold")
        # print(bestAction)
        # Return best action amount pair
        if bestAction == 'fold':
            call_action_info = valid_actions[0]
            action, amount = call_action_info["action"], call_action_info["amount"]
            return action, amount
        if bestAction == "call":
            call_action_info = valid_actions[1]
            action, amount = call_action_info["action"], call_action_info["amount"]
            return action, amount
        if bestAction == "raise":
            call_action_info = valid_actions[2]
            action, amount = call_action_info["action"], call_action_info["amount"]["min"]
            return action, amount

    
    def receive_round_start_message(self, round_count, hole_card, seats):
        pass

    def receive_street_start_message(self, street, round_state):
        pass

    def receive_game_update_message(self, action, round_state):
        pass

    def receive_round_result_message(self, winners, hand_info, round_state):
        pass

    def _setup_game_state(self, round_state, my_hole_card):
        game_state = restore_game_state(round_state)
        game_state['table'].deck.shuffle()
        player_uuids = [player_info['uuid'] for player_info in round_state['seats']]
        for uuid in player_uuids:
            if uuid == self.uuid:
                game_state = attach_hole_card(game_state, uuid, gen_cards(my_hole_card))  # attach my holecard
            else:
                game_state = attach_hole_card_from_deck(game_state, uuid)  # attach opponents holecard at random
        return game_state
