import math
from environment import TerrainType, AntPerception
from ant import AntAction, AntStrategy
from common import Direction

import random


class NonCooperativeStrategy(AntStrategy):

    def __init__(self):
        """Initialize the strategy with last action tracking."""
        self.memory = {}

    def decide_action(self, perception: AntPerception) -> AntAction:
        """Decide an action based on current perception."""
        ant_id = perception.ant_id
        mem = self._get_memory(ant_id)

        if mem["last_action"]== AntAction.MOVE_FORWARD and mem["last_direction"] is not None:
            dx, dy = Direction.get_delta(mem["last_direction"])
            if not mem.get("last_move_blocked", False):
                mem["abs_x"] += dx
                mem["abs_y"] += dy
                if not mem["returning"]:
                    mem["path_history"].append(mem["last_direction"])
            else:
                mem["stuck_count"] += 1

        self._update_memory(mem, perception)

        fwd_Cell = perception.visible_cells.get(Direction.get_delta(perception.direction))
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

        action = self._decide_movement(perception)
        if action == AntAction.MOVE_FORWARD:
            if fwd_Cell == TerrainType.WALL or fwd_Cell is None:
                mem["last_move_blocked"] = True

        mem["last_action"] = action
        mem["last_direction"] = perception.direction if action == AntAction.MOVE_FORWARD else None
        return action


    def _decide_movement(self, perception: AntPerception) -> AntAction:
        """Decide which direction to move based on current state."""
        mem = self._get_memory(perception.ant_id)

        if perception.has_food:
            return self._return_to_colony(mem, perception)
        else:
            return self._seek_food(mem, perception)


    def _get_memory(self, ant_id: int) -> dict:
        if ant_id not in self.memory:
            self.memory[ant_id] = {"visited": set(), "colony_pos": None, "food_targets": [], "abs_x": 0, "abs_y": 0, "last_action": None,
                "last_direction": None,"last_move_blocked": False,"stuck_count": 0,"explore_bias": random.choice([-1, 1]),"path_history": [],
                "returning": False,
                "wander_steps": 0,
            }
        return self.memory[ant_id]


    def _update_memory(self, mem: dict, perception: AntPerception) -> None:
        ax, ay = mem["abs_x"], mem["abs_y"]

        for (dx, dy), terrain in perception.visible_cells.items():
            world_x = ax + dx
            world_y = ay + dy
            mem["visited"].add((world_x, world_y))

            if terrain == TerrainType.COLONY and mem["colony_pos"] is None:
                mem["colony_pos"] = (world_x, world_y)

            if terrain == TerrainType.FOOD:
                pos = (world_x, world_y)
                if pos not in mem["food_targets"]:
                    mem["food_targets"].append(pos)

        to_remove = []
        for pos in mem["food_targets"]:
            rel = (pos[0] - ax, pos[1] - ay)
            if rel in perception.visible_cells:
                if perception.visible_cells[rel] != TerrainType.FOOD:
                    to_remove.append(pos)
        for pos in to_remove:
            mem["food_targets"].remove(pos)


    def _return_to_colony(self, mem: dict, perception: AntPerception) -> AntAction:
        if perception.can_see_colony():
            target_dir_val = perception.get_colony_direction()
            if target_dir_val is not None:
                return self._steer_toward(target_dir_val, perception, mem)

        if mem["path_history"]:
            last_dir = mem["path_history"][-1]
            opposite = Direction((last_dir.value + 4) % 8)
            action = self._steer_toward(opposite.value, perception, mem)
            if action == AntAction.MOVE_FORWARD:
                mem["path_history"].pop()
            return action

        if mem["colony_pos"] is not None:
            dx = mem["colony_pos"][0] - mem["abs_x"]
            dy = mem["colony_pos"][1] - mem["abs_y"]
            if dx == 0 and dy == 0:
                return self._wander(mem, perception)
            target_dir_val = self._delta_to_direction(dx, dy)
            return self._steer_toward(target_dir_val, perception, mem)

        return self._wander(mem, perception)


    def _seek_food(self, mem: dict, perception: AntPerception) -> AntAction:
        if perception.can_see_food():
            mem["wander_steps"] = 0
            target_dir_val = perception.get_food_direction()
            if target_dir_val is not None:
                return self._steer_toward(target_dir_val, perception, mem)

        if mem["food_targets"]:
            mem["wander_steps"] = 0
            target = mem["food_targets"][0]
            dx = target[0] - mem["abs_x"]
            dy = target[1] - mem["abs_y"]
            if dx == 0 and dy == 0:
                mem["food_targets"].pop(0)
                return self._explore(mem, perception)
            target_dir_val = self._delta_to_direction(dx, dy)
            return self._steer_toward(target_dir_val, perception, mem)

        return self._explore(mem, perception)


    def _explore(self, mem: dict, perception: AntPerception) -> AntAction:

        if mem["wander_steps"] > 0:
            mem["wander_steps"] -= 1
            return self._wander(mem, perception)

        ax, ay = mem["abs_x"], mem["abs_y"]
        current_dir = perception.direction

        candidates = [
            (AntAction.MOVE_FORWARD, current_dir)
            ,(AntAction.TURN_LEFT,Direction.get_left(current_dir)),
            (AntAction.TURN_RIGHT, Direction.get_right(current_dir)),
        ]

        best_action = AntAction.MOVE_FORWARD
        best_score = -float("inf")

        for action, direction in candidates:
            score = self._direction_score(ax, ay, direction, mem["visited"], perception)
            if score> best_score:
                best_score = score
                best_action = action

        if best_score <= 0:
            mem["wander_steps"] = random.randint(10, 30)
            mem["explore_bias"] = random.choice([-1, 1])
            return self._wander(mem, perception)

        if mem["stuck_count"] > 3:
            mem["explore_bias"] *= -1
            mem["stuck_count"] = 0
            return AntAction.TURN_LEFT if mem["explore_bias"] == -1 else AntAction.TURN_RIGHT

        if best_action == AntAction.MOVE_FORWARD:
            mem["stuck_count"] = 0

        return best_action


    def _direction_score(self, ax: int, ay: int, direction: Direction, visited: set, perception: AntPerception) -> float:
        dx, dy = Direction.get_delta(direction)
        score = 0.0
        for dist in range(1, 4):
            wx, wy = ax + dx * dist, ay + dy * dist
            rel = (dx * dist, dy * dist)
            if rel in perception.visible_cells:
                if perception.visible_cells[rel] == TerrainType.WALL:
                    score = score -10
                    break
            elif dist == 1:
                score = score - 5
            if (wx, wy) not in visited:
                score = score +  1.0 / dist
        return score

    def _steer_toward(self, target_dir_val: int, perception: AntPerception, mem: dict) -> AntAction:
        current_val = perception.direction.value
        diff = (target_dir_val - current_val ) % 8

        if diff == 0:
            return AntAction.MOVE_FORWARD
        elif diff <= 4:
            return AntAction.TURN_RIGHT
        else:
            return AntAction.TURN_LEFT

    def _wander(self, mem: dict, perception: AntPerception) -> AntAction:
        fwd_Cell = perception.visible_cells.get(Direction.get_delta(perception.direction))

        if fwd_Cell == TerrainType.WALL or fwd_Cell is None:
            return AntAction.TURN_LEFT if mem["explore_bias"] == -1 else AntAction.TURN_RIGHT

        return random.choice([AntAction.MOVE_FORWARD, AntAction.MOVE_FORWARD,AntAction.MOVE_FORWARD, AntAction.TURN_LEFT,AntAction.TURN_RIGHT,])

    
    def _delta_to_direction(self,dx: int, dy: int) -> int:
        angle = math.atan2(dy, dx)
        angle = (angle + math.pi / 2) % (2 * math.pi)
        index = int((angle + math.pi / 8) / (math.pi / 4)) % 8
        return index