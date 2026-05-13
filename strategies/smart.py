from environment import TerrainType, AntPerception
from ant import AntAction, AntStrategy
from common import Direction

import random


class SmartStrategy(AntStrategy):
    def __init__(self):
        self.memory = {}
        self.home_deposit_delay = 5
        self.food_deposit_delay = 2

    def decide_action(self, perception: AntPerception) -> AntAction:
        ant_id = perception.ant_id
        mem = self.get_memory(ant_id)

        if (
            mem["last_action"] == AntAction.MOVE_FORWARD
            and mem["last_direction"] is not None
        ):
            dx, dy = Direction.get_delta(mem["last_direction"])
            if not mem.get("last_move_blocked", False):
                mem["abs_x"] += dx
                mem["abs_y"] += dy
                if not mem["returning"]:
                    mem["path_history"].append(mem["last_direction"])

        ax, ay = mem["abs_x"], mem["abs_y"]
        for (dx, dy), terrain in perception.visible_cells.items():
            world_x = ax + dx
            world_y = ay + dy
            mem["visited"].add((world_x, world_y))

            if terrain == TerrainType.COLONY and mem["colony_pos"] is None:
                mem["colony_pos"] = (world_x, world_y)
        front_cell = perception.visible_cells.get(
            Direction.get_delta(perception.direction)
        )
        mem["last_move_blocked"] = False

        current = perception.visible_cells.get((0, 0))
        if not perception.has_food and current == TerrainType.FOOD:
            mem["last_action"] = AntAction.PICK_UP_FOOD
            mem["last_direction"] = None
            mem["returning"] = True
            return AntAction.PICK_UP_FOOD

        if perception.has_food and current == TerrainType.COLONY:
            mem["last_action"] = AntAction.DROP_FOOD
            mem["last_direction"] = None
            mem["returning"] = False
            mem["path_history"] = []
            return AntAction.DROP_FOOD

        pheromone_action = None
        if perception.has_food:
            if (
                perception.steps_taken > 0
                and perception.steps_taken % self.food_deposit_delay == 0
            ):
                pheromone_action = AntAction.DEPOSIT_FOOD_PHEROMONE
        else:
            if (
                perception.steps_taken > 0
                and perception.steps_taken % self.home_deposit_delay == 0
            ):
                pheromone_action = AntAction.DEPOSIT_HOME_PHEROMONE
        if pheromone_action is not None:
            mem["last_action"] = pheromone_action
            mem["last_direction"] = None
            return pheromone_action

        action = self._decide_movemement(mem, perception)

        if action == AntAction.MOVE_FORWARD:
            if front_cell == TerrainType.WALL or front_cell is None:
                mem["last_move_blocked"] = True

        mem["last_action"] = action
        mem["last_direction"] = (
            perception.direction if action == AntAction.MOVE_FORWARD else None
        )
        return action

    def _decide_movemement(self, mem: dict, perception: AntPerception) -> AntAction:
        """Decide which direction to move based on current state"""

        if perception.has_food:
            return self.return_to_colony(mem, perception)
        else:
            return self.search_food(mem, perception)

    def get_memory(self, ant_id: int) -> dict:
        if ant_id not in self.memory:
            self.memory[ant_id] = {
                "visited": set(),
                "colony_pos": None,
                "abs_x": 0,
                "abs_y": 0,
                "last_action": None,
                "last_direction": None,
                "last_move_blocked": False,
                "explore_bias": random.choice([-1, 1]),
                "path_history": [],
                "returning": False,
            }
        return self.memory[ant_id]

    def return_to_colony(self, mem: dict, perception: AntPerception) -> AntAction:
        if perception.can_see_colony():
            target_direction = perception.get_colony_direction()
            if target_direction is not None:
                return self.move_to_direction(target_direction, perception, mem)

        if mem["path_history"]:
            last_dir = mem["path_history"][-1]
            opposite = Direction((last_dir.value + 4) % 8)
            action = self.move_to_direction(opposite.value, perception, mem)
            if action == AntAction.MOVE_FORWARD:
                mem["path_history"].pop()
            return action

        pheromone_action = self.pheromone_direction(
            perception, perception.home_pheromone, mem
        )
        if pheromone_action is not None:
            return pheromone_action

        if mem["colony_pos"] is not None:
            dx = mem["colony_pos"][0] - mem["abs_x"]
            dy = mem["colony_pos"][1] - mem["abs_y"]
            if dx == 0 and dy == 0:
                front_cell = perception.visible_cells.get(
                    Direction.get_delta(perception.direction)
                )
                if front_cell == TerrainType.WALL or front_cell is None:
                    if mem["explore_bias"] == -1:
                        return AntAction.TURN_LEFT
                    return AntAction.TURN_RIGHT

                return random.choice(
                    [
                        AntAction.MOVE_FORWARD,
                        AntAction.MOVE_FORWARD,
                        AntAction.MOVE_FORWARD,
                        AntAction.TURN_LEFT,
                        AntAction.TURN_RIGHT,
                    ]
                )
            target_direction = self.direction_choice(dx, dy)
            return self.move_to_direction(target_direction, perception, mem)

        front_cell = perception.visible_cells.get(
            Direction.get_delta(perception.direction)
        )
        if front_cell == TerrainType.WALL or front_cell is None:
            if mem["explore_bias"] == -1:
                return AntAction.TURN_LEFT
            return AntAction.TURN_RIGHT

        return random.choice(
            [
                AntAction.MOVE_FORWARD,
                AntAction.MOVE_FORWARD,
                AntAction.MOVE_FORWARD,
                AntAction.TURN_LEFT,
                AntAction.TURN_RIGHT,
            ]
        )

    def search_food(self, mem: dict, perception: AntPerception) -> AntAction:
        if perception.can_see_food():
            target_direction = perception.get_food_direction()
            if target_direction is not None:
                return self.move_to_direction(target_direction, perception, mem)

        pheromone_action = self.pheromone_direction(
            perception, perception.food_pheromone, mem
        )
        if pheromone_action is not None:
            return pheromone_action

        candidates = [
            (AntAction.MOVE_FORWARD, perception.direction),
            (AntAction.TURN_LEFT, Direction.get_left(perception.direction)),
            (AntAction.TURN_RIGHT, Direction.get_right(perception.direction)),
        ]

        possible_actions = []
        new_actions = []

        for action, direction in candidates:
            dx, dy = Direction.get_delta(direction)
            cell = perception.visible_cells.get((dx, dy))
            if cell == TerrainType.WALL or cell is None:
                continue

            next_pos = (mem["abs_x"] + dx, mem["abs_y"] + dy)
            if next_pos not in mem["visited"]:
                if action == AntAction.MOVE_FORWARD:
                    return action
                new_actions.append(action)

            possible_actions.append(action)

        if new_actions:
            return random.choice(new_actions)

        if possible_actions:
            return random.choice(possible_actions)

        return random.choice([AntAction.TURN_LEFT, AntAction.TURN_RIGHT])

    def move_to_direction(
        self, target_direction: int, perception: AntPerception, mem: dict
    ) -> AntAction:
        current_val = perception.direction.value
        diff = (target_direction - current_val) % 8

        if diff == 0:
            front_cell_position = Direction.get_delta(perception.direction)
            front_cell = perception.visible_cells.get(front_cell_position)
            if front_cell == TerrainType.WALL or front_cell is None:
                return (
                    AntAction.TURN_LEFT
                    if mem["explore_bias"] == -1
                    else AntAction.TURN_RIGHT
                )
            return AntAction.MOVE_FORWARD
        elif diff <= 4:
            return AntAction.TURN_RIGHT
        else:
            return AntAction.TURN_LEFT

    def direction_choice(self, dx: int, dy: int) -> int:
        if dx == 0 and dy < 0:
            return Direction.NORTH.value
        if dx > 0 and dy < 0:
            return Direction.NORTHEAST.value
        if dx > 0 and dy == 0:
            return Direction.EAST.value
        if dx > 0 and dy > 0:
            return Direction.SOUTHEAST.value
        if dx == 0 and dy > 0:
            return Direction.SOUTH.value
        if dx < 0 and dy > 0:
            return Direction.SOUTHWEST.value
        if dx < 0 and dy == 0:
            return Direction.WEST.value
        if dx < 0 and dy < 0:
            return Direction.NORTHWEST.value
        return Direction.NORTH.value

    def pheromone_direction(self, perception: AntPerception, pheromones, mem):
        best_pos = None
        best_value = 0
        for pos, value in pheromones.items():
            if pos == (0, 0):
                continue

            cell_type = perception.visible_cells.get(pos)
            if cell_type == TerrainType.WALL:
                continue
            if value > best_value:
                best_value = value
                best_pos = pos

        if best_pos is None:
            return None

        direction = self.direction_choice(best_pos[0], best_pos[1])
        return self.move_to_direction(direction, perception, mem)
