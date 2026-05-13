from environment import TerrainType, AntPerception
from ant import AntAction, AntStrategy
from common import Direction
import random


class CooperativeStrategy(AntStrategy):
    def __init__(self):
        self.home_deposit_delay = 4
        self.food_deposit_delay = 2

    def decide_action(self, perception: AntPerception) -> AntAction:
        """Decide an action based on current perception"""

        curr_cell = perception.visible_cells.get((0, 0))
        if not perception.has_food and curr_cell == TerrainType.FOOD:
            return AntAction.PICK_UP_FOOD
        if perception.has_food and curr_cell == TerrainType.COLONY:
            return AntAction.DROP_FOOD
        if perception.has_food:
            if perception.steps_taken % self.food_deposit_delay == 0:
                return AntAction.DEPOSIT_FOOD_PHEROMONE
        else:
            if perception.steps_taken % self.home_deposit_delay == 0:
                return AntAction.DEPOSIT_HOME_PHEROMONE
        return self._decide_movement(perception)

    def _decide_movement(self, perception: AntPerception) -> AntAction:
        """Decide which direction to move based on current state"""

        if perception.has_food and perception.can_see_colony():
            return self.turn_to_direction(perception, perception.get_colony_direction())
        if (not perception.has_food) and perception.can_see_food():
            return self.turn_to_direction(perception, perception.get_food_direction())
        new_action = 0
        if perception.has_food:
            new_action = self.pheromone_direction(perception, perception.home_pheromone)
            if new_action is not None:
                return new_action
            return self.search_home_pheromone(perception)
        else:
            new_action = self.pheromone_direction(perception, perception.food_pheromone)
            if new_action is not None:
                return new_action

        pos_front_cell = Direction.get_delta(perception.direction)
        type_cell = perception.visible_cells.get(pos_front_cell)
        if type_cell == TerrainType.WALL or type_cell is None:
            return random.choice([AntAction.TURN_LEFT, AntAction.TURN_RIGHT])
        return random.choice(
            [
                AntAction.MOVE_FORWARD,
                AntAction.MOVE_FORWARD,
                AntAction.TURN_LEFT,
                AntAction.TURN_RIGHT,
            ]
        )

    def turn_to_direction(self, perception: AntPerception, direction_value: int):
        # Turn left or right to face the direction we want.
        if direction_value is None:
            return AntAction.MOVE_FORWARD
        where_to_go = (direction_value - perception.direction.value) % 8
        if where_to_go == 0:
            return AntAction.MOVE_FORWARD
        if where_to_go <= 4:
            return AntAction.TURN_RIGHT
        return AntAction.TURN_LEFT

    def pheromone_direction(self, perception: AntPerception, pheromones):
        # Look for the strongest pheromone that the ant can see.
        best_pos = None
        best_value = 0
        for pos, value in pheromones.items():
            cell_type = perception.visible_cells.get(pos)
            if value > best_value and cell_type != TerrainType.WALL:
                best_value = value
                best_pos = pos

        if best_pos is None:
            return None

        x, y = best_pos
        if x == 0 and y < 0:
            return self.turn_to_direction(perception, Direction.NORTH.value)
        if x > 0 and y < 0:
            return self.turn_to_direction(perception, Direction.NORTHEAST.value)
        if x > 0 and y == 0:
            return self.turn_to_direction(perception, Direction.EAST.value)
        if x > 0 and y > 0:
            return self.turn_to_direction(perception, Direction.SOUTHEAST.value)
        if x == 0 and y > 0:
            return self.turn_to_direction(perception, Direction.SOUTH.value)
        if x < 0 and y > 0:
            return self.turn_to_direction(perception, Direction.SOUTHWEST.value)
        if x < 0 and y == 0:
            return self.turn_to_direction(perception, Direction.WEST.value)
        return self.turn_to_direction(perception, Direction.NORTHWEST.value)

    def search_home_pheromone(self, perception: AntPerception):
        # If no home pheromone is visible, try to turn around and search.
        pos_front_cell = Direction.get_delta(perception.direction)
        type_cell = perception.visible_cells.get(pos_front_cell)

        if type_cell == TerrainType.WALL or type_cell is None:
            return random.choice([AntAction.TURN_LEFT, AntAction.TURN_RIGHT])

        if perception.steps_taken % 5 == 0:
            return AntAction.MOVE_FORWARD

        return AntAction.TURN_LEFT
