import pygame
import random
import math
import sys
import heapq

# =========================================================
# INITIAL SETUP
# =========================================================

pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()

WIDTH = 1100
HEIGHT = 700
FPS = 60

WORLD_W = 3200
WORLD_H = 2200

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("DON'T LOOK BEHIND YOU")
clock = pygame.time.Clock()

# =========================================================
# COLORS
# =========================================================

BLACK = (5, 5, 7)
FLOOR = (24, 22, 25)
FLOOR_ALT = (29, 27, 30)
WALL = (48, 45, 50)
WALL_EDGE = (85, 80, 88)

WHITE = (220, 220, 220)
GRAY = (145, 145, 145)

GREEN = (70, 210, 110)
DARK_GREEN = (30, 100, 55)

RED = (180, 45, 45)
DARK_RED = (80, 15, 20)

YELLOW = (235, 205, 60)
BLUE = (80, 150, 210)

# =========================================================
# GAME SETTINGS
# =========================================================

GAME_TIME = 5 * 60

PLAYER_SPEED = 200
PLAYER_RADIUS = 13

CREATURE_RADIUS = 17

# Pathfinding grid
PATH_GRID = 100
PATH_RECALC_TIME = 0.8

# Main building boundary thickness
BOUNDARY = 115

# =========================================================
# FONTS
# =========================================================

font = pygame.font.SysFont("consolas", 22)
small_font = pygame.font.SysFont("consolas", 17)
big_font = pygame.font.SysFont("consolas", 54, bold=True)

# =========================================================
# SIMPLE SOUNDS
# =========================================================

def make_tone(frequency, duration, volume=0.15):
    sample_rate = 44100
    count = int(sample_rate * duration)

    samples = []

    for i in range(count):
        value = int(
            32767
            * volume
            * math.sin(2 * math.pi * frequency * i / sample_rate)
        )

        samples.append(value)

    stereo = []
    for value in samples:
        stereo.append(value)
        stereo.append(value)

    return pygame.mixer.Sound(
        buffer=bytes(
            (x & 0xFF for x in [])
        )
    )


# Safer generated sounds
def create_beep(frequency, duration, volume=0.12):
    sample_rate = 44100
    count = int(sample_rate * duration)

    data = bytearray()

    for i in range(count):
        value = int(
            32767
            * volume
            * math.sin(2 * math.pi * frequency * i / sample_rate)
        )

        value = max(-32768, min(32767, value))

        data += int(value).to_bytes(2, "little", signed=True)
        data += int(value).to_bytes(2, "little", signed=True)

    return pygame.mixer.Sound(buffer=bytes(data))


def create_noise(duration=0.15, volume=0.08):
    sample_rate = 44100
    count = int(sample_rate * duration)

    data = bytearray()

    for _ in range(count):
        value = random.randint(-32768, 32767)
        value = int(value * volume)

        data += int(value).to_bytes(2, "little", signed=True)
        data += int(value).to_bytes(2, "little", signed=True)

    return pygame.mixer.Sound(buffer=bytes(data))


sound_power = create_beep(110, 0.35, 0.16)
sound_key = create_beep(700, 0.18, 0.12)
sound_bang = create_beep(65, 0.20, 0.15)
sound_static = create_noise(0.12, 0.05)

# =========================================================
# WORLD VARIABLES
# =========================================================

outer_walls = []
walls = []
rooms = []

key_room = None
key_gate = None

power_room = None
power_position = pygame.Vector2()

key_position = pygame.Vector2()

escape = pygame.Rect(0, 0, 80, 80)

random_walls = []

# =========================================================
# PLAYER / CREATURE
# =========================================================

player = pygame.Vector2()
creature = pygame.Vector2()

creature_chasing = False
creature_path = []
creature_path_timer = 0

# =========================================================
# GAME STATE
# =========================================================

power_on = False
key_collected = False

game_won = False
game_lost = False

game_start = 0

message = ""
message_timer = 0

camera = pygame.Vector2()

# =========================================================
# PATHFINDING GRID
# =========================================================

path_blocked = set()

# =========================================================
# FLASHLIGHT
# =========================================================

flashlight_overlay = pygame.Surface(
    (WIDTH, HEIGHT),
    pygame.SRCALPHA
)

# =========================================================
# ROOM POSITIONS
# =========================================================

ROOM_SLOTS = [
    pygame.Rect(180, 180, 430, 300),
    pygame.Rect(850, 170, 430, 300),
    pygame.Rect(1530, 180, 430, 300),

    pygame.Rect(280, 780, 430, 300),
    pygame.Rect(1050, 700, 430, 300),
    pygame.Rect(1800, 760, 430, 300),

    pygame.Rect(650, 1320, 430, 300),
    pygame.Rect(1450, 1350, 430, 300),
    pygame.Rect(2250, 1300, 430, 300),

    pygame.Rect(850, 1800, 430, 260),
    pygame.Rect(1700, 1810, 430, 260),
]


# =========================================================
# COLLISION
# =========================================================

def circle_hits_rect(position, radius, rect):
    closest_x = max(rect.left, min(position.x, rect.right))
    closest_y = max(rect.top, min(position.y, rect.bottom))

    dx = position.x - closest_x
    dy = position.y - closest_y

    return dx * dx + dy * dy < radius * radius


def position_blocked(position):
    # Main building boundary
    if position.x - PLAYER_RADIUS < BOUNDARY:
        return True

    if position.x + PLAYER_RADIUS > WORLD_W - BOUNDARY:
        return True

    if position.y - PLAYER_RADIUS < BOUNDARY:
        return True

    if position.y + PLAYER_RADIUS > WORLD_H - BOUNDARY:
        return True

    # Walls
    for wall in walls:
        if circle_hits_rect(position, PLAYER_RADIUS, wall):
            return True

    # Key room gate
    if not power_on and key_gate is not None:
        if circle_hits_rect(position, PLAYER_RADIUS, key_gate):
            return True

    return False


def creature_position_blocked(position):
    # Creature boundary
    if position.x - CREATURE_RADIUS < BOUNDARY:
        return True

    if position.x + CREATURE_RADIUS > WORLD_W - BOUNDARY:
        return True

    if position.y - CREATURE_RADIUS < BOUNDARY:
        return True

    if position.y + CREATURE_RADIUS > WORLD_H - BOUNDARY:
        return True

    for wall in walls:
        if circle_hits_rect(position, CREATURE_RADIUS, wall):
            return True

    if not power_on and key_gate is not None:
        if circle_hits_rect(position, CREATURE_RADIUS, key_gate):
            return True

    return False


# =========================================================
# ROOM GATES
# =========================================================

def choose_gate(rect):
    """
    Pick a gate facing INTO the map.

    This prevents gates from being placed directly
    against the outside boundary.
    """

    center_x = rect.centerx
    center_y = rect.centery

    # Near LEFT boundary -> gate on RIGHT
    if rect.left < 450:
        return pygame.Rect(
            rect.right - 1,
            center_y - 50,
            35,
            100
        )

    # Near RIGHT boundary -> gate on LEFT
    if rect.right > WORLD_W - 450:
        return pygame.Rect(
            rect.left - 34,
            center_y - 50,
            35,
            100
        )

    # Near TOP boundary -> gate on BOTTOM
    if rect.top < 450:
        return pygame.Rect(
            center_x - 50,
            rect.bottom - 1,
            100,
            35
        )

    # Near BOTTOM boundary -> gate on TOP
    if rect.bottom > WORLD_H - 450:
        return pygame.Rect(
            center_x - 50,
            rect.top - 34,
            100,
            35
        )

    # Middle rooms -> bottom gate
    return pygame.Rect(
        center_x - 50,
        rect.bottom - 1,
        100,
        35
    )


def build_room_walls(room):
    """
    Build walls around a room while leaving
    an opening wherever its gate is.
    """

    r = room["rect"]
    g = room["gate"]

    # -------------------------
    # TOP
    # -------------------------

    if g.top <= r.top + 35:
        walls.append(
            pygame.Rect(
                r.x,
                r.y,
                max(0, g.left - r.x),
                30
            )
        )

        walls.append(
            pygame.Rect(
                g.right,
                r.y,
                max(0, r.right - g.right),
                30
            )
        )
    else:
        walls.append(
            pygame.Rect(
                r.x,
                r.y,
                r.width,
                30
            )
        )

    # -------------------------
    # BOTTOM
    # -------------------------

    if g.bottom >= r.bottom - 35:
        walls.append(
            pygame.Rect(
                r.x,
                r.bottom - 30,
                max(0, g.left - r.x),
                30
            )
        )

        walls.append(
            pygame.Rect(
                g.right,
                r.bottom - 30,
                max(0, r.right - g.right),
                30
            )
        )
    else:
        walls.append(
            pygame.Rect(
                r.x,
                r.bottom - 30,
                r.width,
                30
            )
        )

    # -------------------------
    # LEFT
    # -------------------------

    if g.left <= r.left + 35:
        walls.append(
            pygame.Rect(
                r.x,
                r.y,
                30,
                max(0, g.top - r.y)
            )
        )

        walls.append(
            pygame.Rect(
                r.x,
                g.bottom,
                30,
                max(0, r.bottom - g.bottom)
            )
        )
    else:
        walls.append(
            pygame.Rect(
                r.x,
                r.y,
                30,
                r.height
            )
        )

    # -------------------------
    # RIGHT
    # -------------------------

    if g.right >= r.right - 35:
        walls.append(
            pygame.Rect(
                r.right - 30,
                r.y,
                30,
                max(0, g.top - r.y)
            )
        )

        walls.append(
            pygame.Rect(
                r.right - 30,
                g.bottom,
                30,
                max(0, r.bottom - g.bottom)
            )
        )
    else:
        walls.append(
            pygame.Rect(
                r.right - 30,
                r.y,
                30,
                r.height
            )
        )


def build_key_room_walls():
    """
    Key room gets the same intelligent gate system.
    Only its gate opens when power is activated.
    """

    r = key_room
    g = key_gate

    # TOP
    if g.top <= r.top + 35:
        walls.append(
            pygame.Rect(
                r.x,
                r.y,
                max(0, g.left - r.x),
                30
            )
        )

        walls.append(
            pygame.Rect(
                g.right,
                r.y,
                max(0, r.right - g.right),
                30
            )
        )
    else:
        walls.append(
            pygame.Rect(
                r.x,
                r.y,
                r.width,
                30
            )
        )

    # BOTTOM
    if g.bottom >= r.bottom - 35:
        walls.append(
            pygame.Rect(
                r.x,
                r.bottom - 30,
                max(0, g.left - r.x),
                30
            )
        )

        walls.append(
            pygame.Rect(
                g.right,
                r.bottom - 30,
                max(0, r.right - g.right),
                30
            )
        )
    else:
        walls.append(
            pygame.Rect(
                r.x,
                r.bottom - 30,
                r.width,
                30
            )
        )

    # LEFT
    if g.left <= r.left + 35:
        walls.append(
            pygame.Rect(
                r.x,
                r.y,
                30,
                max(0, g.top - r.y)
            )
        )

        walls.append(
            pygame.Rect(
                r.x,
                g.bottom,
                30,
                max(0, r.bottom - g.bottom)
            )
        )
    else:
        walls.append(
            pygame.Rect(
                r.x,
                r.y,
                30,
                r.height
            )
        )

    # RIGHT
    if g.right >= r.right - 35:
        walls.append(
            pygame.Rect(
                r.right - 30,
                r.y,
                30,
                max(0, g.top - r.y)
            )
        )

        walls.append(
            pygame.Rect(
                r.right - 30,
                g.bottom,
                30,
                max(0, r.bottom - g.bottom)
            )
        )
    else:
        walls.append(
            pygame.Rect(
                r.right - 30,
                r.y,
                30,
                r.height
            )
        )


# =========================================================
# RANDOM INTERIOR WALLS
# =========================================================

def generate_random_walls():
    global random_walls

    random_walls = []

    candidates = []

    for _ in range(35):
        width = random.choice([100, 120, 140, 160])
        height = random.choice([30, 35, 40])

        x = random.randint(
            BOUNDARY + 120,
            WORLD_W - BOUNDARY - width - 120
        )

        y = random.randint(
            BOUNDARY + 120,
            WORLD_H - BOUNDARY - height - 120
        )

        candidates.append(
            pygame.Rect(x, y, width, height)
        )

    random.shuffle(candidates)

    for candidate in candidates:

        # Don't put random walls through rooms
        bad = False

        for room in rooms:
            if candidate.colliderect(
                room["rect"].inflate(70, 70)
            ):
                bad = True
                break

        if bad:
            continue

        # Don't block key room
        if key_room and candidate.colliderect(
            key_room.inflate(80, 80)
        ):
            continue

        # Don't put walls too close together
        too_close = False

        for existing in random_walls:
            if candidate.inflate(35, 35).colliderect(existing):
                too_close = True
                break

        if too_close:
            continue

        random_walls.append(candidate)

        if len(random_walls) >= 10:
            break


# =========================================================
# RANDOM EXIT
# =========================================================

def generate_exit():
    global escape

    for _ in range(100):

        side = random.choice(
            ["top", "bottom", "left", "right"]
        )

        if side == "top":
            x = random.randint(
                BOUNDARY + 150,
                WORLD_W - BOUNDARY - 150
            )

            candidate = pygame.Rect(
                x,
                BOUNDARY - 5,
                90,
                70
            )

        elif side == "bottom":
            x = random.randint(
                BOUNDARY + 150,
                WORLD_W - BOUNDARY - 150
            )

            candidate = pygame.Rect(
                x,
                WORLD_H - BOUNDARY - 65,
                90,
                70
            )

        elif side == "left":
            y = random.randint(
                BOUNDARY + 150,
                WORLD_H - BOUNDARY - 150
            )

            candidate = pygame.Rect(
                BOUNDARY - 5,
                y,
                70,
                90
            )

        else:
            y = random.randint(
                BOUNDARY + 150,
                WORLD_H - BOUNDARY - 150
            )

            candidate = pygame.Rect(
                WORLD_W - BOUNDARY - 65,
                y,
                70,
                90
            )

        # Keep exit away from rooms
        blocked = False

        for room in rooms:
            if candidate.colliderect(
                room["rect"].inflate(50, 50)
            ):
                blocked = True
                break

        if key_room and candidate.colliderect(
            key_room.inflate(50, 50)
        ):
            blocked = True

        if not blocked:
            escape = candidate
            return

    # Fallback
    escape = pygame.Rect(
        WORLD_W - BOUNDARY - 80,
        WORLD_H // 2 - 40,
        70,
        80
    )


# =========================================================
# CREATE WORLD
# =========================================================

def create_world():
    global walls
    global outer_walls
    global rooms
    global key_room
    global key_gate
    global power_room
    global power_position
    global key_position

    walls = []
    outer_walls = []
    rooms = []

    # -----------------------------------------------------
    # OUTER BOUNDARY
    # -----------------------------------------------------

    outer_walls = [
        pygame.Rect(
            80,
            80,
            WORLD_W - 160,
            35
        ),

        pygame.Rect(
            80,
            WORLD_H - 115,
            WORLD_W - 160,
            35
        ),

        pygame.Rect(
            80,
            80,
            35,
            WORLD_H - 160
        ),

        pygame.Rect(
            WORLD_W - 115,
            80,
            35,
            WORLD_H - 160
        )
    ]

    # -----------------------------------------------------
    # RANDOM ROOMS
    # -----------------------------------------------------

    slots = ROOM_SLOTS.copy()
    random.shuffle(slots)

    selected = slots[:5]

    names = ["A", "B", "C", "D", "E"]

    for i, rect in enumerate(selected):

        room = {
            "name": names[i],
            "rect": rect.copy(),
            "gate": choose_gate(rect)
        }

        rooms.append(room)

    # -----------------------------------------------------
    # RANDOM KEY ROOM
    # -----------------------------------------------------

    key_room_data = random.choice(rooms)

    key_room = key_room_data["rect"].copy()
    key_gate = key_room_data["gate"].copy()

    # -----------------------------------------------------
    # RANDOM POWER ROOM
    # -----------------------------------------------------

    possible_power_rooms = [
        room
        for room in rooms
        if room is not key_room_data
    ]

    power_room = random.choice(possible_power_rooms)

    power_position = pygame.Vector2(
        power_room["rect"].centerx,
        power_room["rect"].centery
    )

    key_position = pygame.Vector2(
        key_room.centerx,
        key_room.centery
    )

    # -----------------------------------------------------
    # BUILD ROOM WALLS
    # -----------------------------------------------------

    for room in rooms:

        if room is key_room_data:
            continue

        build_room_walls(room)

    build_key_room_walls()

    # -----------------------------------------------------
    # RANDOM WALLS
    # -----------------------------------------------------

    generate_random_walls()

    walls.extend(random_walls)

    # -----------------------------------------------------
    # EXIT
    # -----------------------------------------------------

    generate_exit()


# =========================================================
# ROOM UTILITIES
# =========================================================

def room_center(room):
    r = room["rect"]

    return pygame.Vector2(
        r.centerx,
        r.centery
    )


# =========================================================
# PLAYER / CREATURE START
# =========================================================

def reset_positions():

    global player
    global creature

    # Player cannot start inside key/power rooms
    valid_rooms = [
        room
        for room in rooms
        if room["rect"] != key_room
        and room is not power_room
    ]

    if not valid_rooms:
        valid_rooms = rooms

    start_room = random.choice(valid_rooms)

    player = room_center(start_room)

    # Move player away from center
    player.y -= 45

    # Creature gets a distant random position
    possible_positions = []

    for _ in range(100):

        x = random.randint(
            BOUNDARY + 100,
            WORLD_W - BOUNDARY - 100
        )

        y = random.randint(
            BOUNDARY + 100,
            WORLD_H - BOUNDARY - 100
        )

        candidate = pygame.Vector2(x, y)

        if candidate.distance_to(player) < 900:
            continue

        if creature_position_blocked(candidate):
            continue

        possible_positions.append(candidate)

        if len(possible_positions) >= 1:
            break

    if possible_positions:
        creature = possible_positions[0]

    else:
        creature = pygame.Vector2(
            WORLD_W - 300,
            WORLD_H - 300
        )


# =========================================================
# PATH GRID
# =========================================================

def build_path_grid():

    global path_blocked

    path_blocked = set()

    max_x = WORLD_W // PATH_GRID
    max_y = WORLD_H // PATH_GRID

    for y in range(max_y):

        for x in range(max_x):

            center = pygame.Vector2(
                x * PATH_GRID + PATH_GRID / 2,
                y * PATH_GRID + PATH_GRID / 2
            )

            if creature_position_blocked(center):
                path_blocked.add((x, y))


def nearest_open_cell(cell):

    max_x = WORLD_W // PATH_GRID
    max_y = WORLD_H // PATH_GRID

    x, y = cell

    if (
        0 <= x < max_x
        and 0 <= y < max_y
        and cell not in path_blocked
    ):
        return cell

    for radius in range(1, 5):

        for dx in range(-radius, radius + 1):

            for dy in range(-radius, radius + 1):

                candidate = (
                    x + dx,
                    y + dy
                )

                cx, cy = candidate

                if (
                    0 <= cx < max_x
                    and 0 <= cy < max_y
                    and candidate not in path_blocked
                ):
                    return candidate

    return None


def find_creature_path(start, target):

    max_x = WORLD_W // PATH_GRID
    max_y = WORLD_H // PATH_GRID

    start_cell = (
        int(start.x // PATH_GRID),
        int(start.y // PATH_GRID)
    )

    target_cell = (
        int(target.x // PATH_GRID),
        int(target.y // PATH_GRID)
    )

    start_cell = nearest_open_cell(start_cell)
    target_cell = nearest_open_cell(target_cell)

    if start_cell is None or target_cell is None:
        return []

    if start_cell == target_cell:
        return []

    # A* algorithm
    open_heap = []

    heapq.heappush(
        open_heap,
        (0, start_cell)
    )

    came_from = {}

    g_score = {
        start_cell: 0
    }

    def heuristic(a, b):
        dx = abs(a[0] - b[0])
        dy = abs(a[1] - b[1])

        return math.sqrt(
            dx * dx + dy * dy
        )

    directions = [
        (-1, 0),
        (1, 0),
        (0, -1),
        (0, 1),

        (-1, -1),
        (-1, 1),
        (1, -1),
        (1, 1)
    ]

    visited = set()

    while open_heap:

        _, current = heapq.heappop(open_heap)

        if current in visited:
            continue

        visited.add(current)

        if current == target_cell:

            path = []

            while current in came_from:

                path.append(current)

                current = came_from[current]

            path.reverse()

            result = []

            for cell in path:

                result.append(
                    pygame.Vector2(
                        cell[0] * PATH_GRID
                        + PATH_GRID / 2,

                        cell[1] * PATH_GRID
                        + PATH_GRID / 2
                    )
                )

            return result

        for dx, dy in directions:

            nx = current[0] + dx
            ny = current[1] + dy

            neighbor = (nx, ny)

            if nx < 0 or nx >= max_x:
                continue

            if ny < 0 or ny >= max_y:
                continue

            if neighbor in path_blocked:
                continue

            # Prevent diagonal corner cutting
            if dx != 0 and dy != 0:

                side_a = (
                    current[0] + dx,
                    current[1]
                )

                side_b = (
                    current[0],
                    current[1] + dy
                )

                if (
                    side_a in path_blocked
                    or side_b in path_blocked
                ):
                    continue

            movement_cost = (
                1.414
                if dx != 0 and dy != 0
                else 1
            )

            new_cost = (
                g_score[current]
                + movement_cost
            )

            if (
                neighbor not in g_score
                or new_cost < g_score[neighbor]
            ):

                g_score[neighbor] = new_cost

                priority = (
                    new_cost
                    + heuristic(
                        neighbor,
                        target_cell
                    )
                )

                came_from[neighbor] = current

                heapq.heappush(
                    open_heap,
                    (priority, neighbor)
                )

    return []


# =========================================================
# RESET GAME
# =========================================================

def reset_game():

    global power_on
    global key_collected
    global game_won
    global game_lost

    global game_start
    global message
    global message_timer

    global creature_chasing
    global creature_path
    global creature_path_timer

    create_world()

    power_on = False
    key_collected = False

    game_won = False
    game_lost = False

    creature_chasing = False
    creature_path = []
    creature_path_timer = 0

    message = ""
    message_timer = 0

    reset_positions()

    build_path_grid()

    game_start = pygame.time.get_ticks()


# =========================================================
# CREATURE
# =========================================================

def update_creature(dt, elapsed):

    global creature
    global creature_chasing
    global creature_path
    global creature_path_timer
    global game_lost

    # Distance from creature to player
    distance = creature.distance_to(player)

    # -----------------------------------------------------
    # CREATURE SPEED
    # -----------------------------------------------------

    if elapsed < 120:
        speed = 65

    elif elapsed < 180:
        speed = 75

    elif elapsed < 240:
        speed = 85

    elif elapsed < 300:
        speed = 95

    else:
        speed = 105

    # Power makes it more aggressive
    if power_on:
        speed += 10

    # Key starts the final chase
    if key_collected:
        speed += 15

    # -----------------------------------------------------
    # DETECTION RANGE
    # -----------------------------------------------------

    if elapsed < 120:
        detection = 650

    elif elapsed < 180:
        detection = 800

    elif elapsed < 240:
        detection = 950

    else:
        detection = 1100

    if power_on:
        detection += 200

    if key_collected:
        detection += 400

    # Start chasing when close enough
    if distance < detection:
        creature_chasing = True

    # -----------------------------------------------------
    # CHASE PLAYER
    # -----------------------------------------------------

    if creature_chasing:

        creature_path_timer -= dt

        # Recalculate path periodically
        if creature_path_timer <= 0:

            creature_path = find_creature_path(
                creature,
                player
            )

            creature_path_timer = PATH_RECALC_TIME

        # Follow path
        if creature_path:

            target = creature_path[0]

            direction = target - creature

            # Reached this waypoint
            if direction.length() < 30:

                creature_path.pop(0)

            else:

                direction.normalize()

                movement = (
                    direction
                    * speed
                    * dt
                )

                new_position = creature + movement

                # Only move if not inside a wall
                if not creature_position_blocked(
                    new_position
                ):

                    creature = new_position

                else:

                    # Something blocked the route
                    # so force a new path
                    creature_path = []
                    creature_path_timer = 0

        else:

            # No path found -> try again soon
            creature_path_timer = 0.2

    # -----------------------------------------------------
    # CHECK IF CREATURE CAUGHT PLAYER
    # -----------------------------------------------------

    distance = creature.distance_to(player)

    if distance < PLAYER_RADIUS + CREATURE_RADIUS + 8:

        game_lost = True

# =========================================================
# PLAYER
# =========================================================

def update_player(dt):

    keys = pygame.key.get_pressed()

    direction = pygame.Vector2(0, 0)

    if keys[pygame.K_w] or keys[pygame.K_UP]:
        direction.y -= 1

    if keys[pygame.K_s] or keys[pygame.K_DOWN]:
        direction.y += 1

    if keys[pygame.K_a] or keys[pygame.K_LEFT]:
        direction.x -= 1

    if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
        direction.x += 1

    if direction.length() > 0:
        direction.normalize()

        movement = (
            direction
            * PLAYER_SPEED
            * dt
        )

        # X movement
        new_x = pygame.Vector2(
            player.x + movement.x,
            player.y
        )

        if not position_blocked(new_x):
            player.x = new_x.x

        # Y movement
        new_y = pygame.Vector2(
            player.x,
            player.y + movement.y
        )

        if not position_blocked(new_y):
            player.y = new_y.y


# =========================================================
# INTERACTION
# =========================================================

def interact():

    global power_on
    global key_collected
    global message
    global message_timer
    global path_blocked

    # Power switch
    if not power_on:

        distance = player.distance_to(
            power_position
        )

        if distance < 70:

            power_on = True

            message = "POWER RESTORED"
            message_timer = 3

            pygame.mixer.Sound.play(
                sound_power
            )

            # Key gate is now open
            build_path_grid()

            return

    # Key
    if power_on and not key_collected:

        distance = player.distance_to(
            key_position
        )

        if distance < 65:

            key_collected = True

            message = "YOU FOUND THE KEY"
            message_timer = 3

            pygame.mixer.Sound.play(
                sound_key
            )

            return


# =========================================================
# CAMERA
# =========================================================

def update_camera():

    camera.x = player.x - WIDTH / 2
    camera.y = player.y - HEIGHT / 2

    camera.x = max(
        0,
        min(
            camera.x,
            WORLD_W - WIDTH
        )
    )

    camera.y = max(
        0,
        min(
            camera.y,
            WORLD_H - HEIGHT
        )
    )


# =========================================================
# WORLD DRAWING
# =========================================================

def world_to_screen_rect(rect):

    return pygame.Rect(
        int(rect.x - camera.x),
        int(rect.y - camera.y),
        rect.width,
        rect.height
    )


def draw_world():

    screen.fill(FLOOR)

    # -----------------------------------------------------
    # FLOOR GRID
    # -----------------------------------------------------

    grid_size = 100

    start_x = int(camera.x // grid_size) * grid_size
    end_x = int(camera.x + WIDTH) + grid_size

    start_y = int(camera.y // grid_size) * grid_size
    end_y = int(camera.y + HEIGHT) + grid_size

    for x in range(start_x, end_x, grid_size):

        sx = int(x - camera.x)

        pygame.draw.line(
            screen,
            (32, 30, 34),
            (sx, 0),
            (sx, HEIGHT)
        )

    for y in range(start_y, end_y, grid_size):

        sy = int(y - camera.y)

        pygame.draw.line(
            screen,
            (32, 30, 34),
            (0, sy),
            (WIDTH, sy)
        )

    # -----------------------------------------------------
    # ROOMS
    # -----------------------------------------------------

    for room in rooms:

        r = world_to_screen_rect(
            room["rect"]
        )

        if room["rect"] == key_room:
            pygame.draw.rect(
                screen,
                (30, 25, 30),
                r
            )
        else:
            pygame.draw.rect(
                screen,
                FLOOR_ALT,
                r
            )

    # -----------------------------------------------------
    # OUTER WALLS
    # -----------------------------------------------------

    for wall in outer_walls:

        r = world_to_screen_rect(wall)

        pygame.draw.rect(
            screen,
            WALL,
            r
        )

        pygame.draw.rect(
            screen,
            WALL_EDGE,
            r,
            2
        )

    # -----------------------------------------------------
    # INTERIOR WALLS
    # -----------------------------------------------------

    for wall in walls:

        r = world_to_screen_rect(wall)

        pygame.draw.rect(
            screen,
            WALL,
            r
        )

        pygame.draw.rect(
            screen,
            WALL_EDGE,
            r,
            1
        )

    # -----------------------------------------------------
    # NORMAL ROOM GATES
    # -----------------------------------------------------

    for room in rooms:

        if room["rect"] == key_room:
            continue

        gate = world_to_screen_rect(
            room["gate"]
        )

        pygame.draw.rect(
            screen,
            DARK_GREEN,
            gate
        )

        pygame.draw.rect(
            screen,
            GREEN,
            gate,
            2
        )

    # -----------------------------------------------------
    # KEY GATE
    # -----------------------------------------------------

    if key_gate:

        gate = world_to_screen_rect(
            key_gate
        )

        if power_on:
            pygame.draw.rect(
                screen,
                DARK_GREEN,
                gate
            )

            pygame.draw.rect(
                screen,
                GREEN,
                gate,
                2
            )

        else:
            pygame.draw.rect(
                screen,
                DARK_RED,
                gate
            )

            pygame.draw.rect(
                screen,
                RED,
                gate,
                2
            )

    # -----------------------------------------------------
    # POWER SWITCH
    # -----------------------------------------------------

    power_screen = pygame.Vector2(
        power_position.x - camera.x,
        power_position.y - camera.y
    )

    pygame.draw.circle(
        screen,
        DARK_GREEN if power_on else RED,
        (
            int(power_screen.x),
            int(power_screen.y)
        ),
        18
    )

    pygame.draw.circle(
        screen,
        GREEN if power_on else RED,
        (
            int(power_screen.x),
            int(power_screen.y)
        ),
        11
    )

    # -----------------------------------------------------
    # KEY
    # -----------------------------------------------------

    if power_on and not key_collected:

        key_screen = pygame.Vector2(
            key_position.x - camera.x,
            key_position.y - camera.y
        )

        kx = int(key_screen.x)
        ky = int(key_screen.y)

        pygame.draw.circle(
            screen,
            YELLOW,
            (kx, ky),
            9
        )

        pygame.draw.line(
            screen,
            YELLOW,
            (kx + 6, ky),
            (kx + 25, ky),
            5
        )

        pygame.draw.line(
            screen,
            YELLOW,
            (kx + 18, ky),
            (kx + 18, ky + 8),
            4
        )

        pygame.draw.line(
            screen,
            YELLOW,
            (kx + 25, ky),
            (kx + 25, ky + 8),
            4
        )

    # -----------------------------------------------------
    # EXIT
    # -----------------------------------------------------

    exit_screen = world_to_screen_rect(
        escape
    )

    if key_collected:
        pygame.draw.rect(
            screen,
            DARK_GREEN,
            exit_screen
        )

        pygame.draw.rect(
            screen,
            GREEN,
            exit_screen,
            3
        )

    else:
        pygame.draw.rect(
            screen,
            (40, 35, 35),
            exit_screen
        )

        pygame.draw.rect(
            screen,
            (90, 70, 70),
            exit_screen,
            2
        )


# =========================================================
# PLAYER DRAWING
# =========================================================

def draw_player():

    pos = (
        int(player.x - camera.x),
        int(player.y - camera.y)
    )

    pygame.draw.circle(
        screen,
        BLUE,
        pos,
        PLAYER_RADIUS
    )

    pygame.draw.circle(
        screen,
        WHITE,
        pos,
        PLAYER_RADIUS,
        2
    )


# =========================================================
# CREATURE DRAWING
# =========================================================

def draw_creature():

    pos = (
        int(creature.x - camera.x),
        int(creature.y - camera.y)
    )

    # Shadow
    pygame.draw.circle(
        screen,
        (8, 8, 10),
        pos,
        CREATURE_RADIUS + 5
    )

    # Creature
    pygame.draw.circle(
        screen,
        (18, 18, 20),
        pos,
        CREATURE_RADIUS
    )

    # Eyes
    pygame.draw.circle(
        screen,
        RED,
        (pos[0] - 6, pos[1] - 4),
        3
    )

    pygame.draw.circle(
        screen,
        RED,
        (pos[0] + 6, pos[1] - 4),
        3
    )


# =========================================================
# FLASHLIGHT / DARKNESS
# =========================================================

def draw_darkness(elapsed):

    # Difficulty increases over time

    if elapsed < 120:
        darkness = 205
        radius = 230

    elif elapsed < 180:
        darkness = 220
        radius = 210

    elif elapsed < 240:
        darkness = 235
        radius = 185

    else:
        darkness = 245
        radius = 160

    if power_on:
        radius -= 15

    if key_collected:
        radius -= 25

    radius = max(110, radius)

    flashlight_overlay.fill(
        (0, 0, 0, darkness)
    )

    mouse_x, mouse_y = pygame.mouse.get_pos()

    # Main light
    pygame.draw.circle(
        flashlight_overlay,
        (0, 0, 0, 0),
        (mouse_x, mouse_y),
        radius
    )

    # Softer outer light
    pygame.draw.circle(
        flashlight_overlay,
        (0, 0, 0, 70),
        (mouse_x, mouse_y),
        int(radius * 1.35)
    )

    screen.blit(
        flashlight_overlay,
        (0, 0)
    )


# =========================================================
# UI
# =========================================================

def draw_ui(elapsed):

    remaining = max(
        0,
        GAME_TIME - elapsed
    )

    minutes = int(remaining) // 60
    seconds = int(remaining) % 60

    timer_text = font.render(
        f"{minutes}:{seconds:02d}",
        True,
        WHITE
    )

    screen.blit(
        timer_text,
        (25, 20)
    )

    # Objective
    if not power_on:

        objective = "FIND THE POWER"

    elif not key_collected:

        objective = "FIND THE KEY"

    else:

        objective = "ESCAPE"

    objective_text = small_font.render(
        objective,
        True,
        WHITE
    )

    screen.blit(
        objective_text,
        (25, 52)
    )

    # Interaction hints
    if not power_on:

        if player.distance_to(power_position) < 100:

            text = small_font.render(
                "E - POWER",
                True,
                GREEN
            )

            screen.blit(
                text,
                (25, HEIGHT - 45)
            )

    elif not key_collected:

        if player.distance_to(key_position) < 100:

            text = small_font.render(
                "E - TAKE KEY",
                True,
                YELLOW
            )

            screen.blit(
                text,
                (25, HEIGHT - 45)
            )

    else:

        text = small_font.render(
            "GET TO THE EXIT",
            True,
            GREEN
        )

        screen.blit(
            text,
            (25, HEIGHT - 45)
        )

    # Message
    if message_timer > 0:

        msg = font.render(
            message,
            True,
            WHITE
        )

        screen.blit(
            msg,
            (
                WIDTH // 2 - msg.get_width() // 2,
                25
            )
        )


# =========================================================
# AUDIO
# =========================================================

def update_audio(elapsed):

    # Occasional analog horror sounds
    chance = 0.0015

    if power_on:
        chance = 0.0025

    if key_collected:
        chance = 0.004

    if random.random() < chance:

        sound = random.choice([
            sound_bang,
            sound_static
        ])

        pygame.mixer.Sound.play(sound)


# =========================================================
# TITLE SCREEN
# =========================================================

def title_screen():

    waiting = True

    while waiting:

        screen.fill(BLACK)

        title = big_font.render(
            "DON'T LOOK BEHIND YOU",
            True,
            WHITE
        )

        screen.blit(
            title,
            (
                WIDTH // 2 - title.get_width() // 2,
                HEIGHT // 2 - 100
            )
        )

        subtitle = font.render(
            "WASD / ARROWS TO MOVE",
            True,
            GRAY
        )

        screen.blit(
            subtitle,
            (
                WIDTH // 2 - subtitle.get_width() // 2,
                HEIGHT // 2
            )
        )

        subtitle2 = font.render(
            "E TO INTERACT",
            True,
            GRAY
        )

        screen.blit(
            subtitle2,
            (
                WIDTH // 2 - subtitle2.get_width() // 2,
                HEIGHT // 2 + 35
            )
        )

        start = font.render(
            "PRESS ENTER TO BEGIN",
            True,
            GREEN
        )

        screen.blit(
            start,
            (
                WIDTH // 2 - start.get_width() // 2,
                HEIGHT // 2 + 110
            )
        )

        pygame.display.flip()

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:

                if event.key == pygame.K_RETURN:
                    waiting = False


# =========================================================
# END SCREEN
# =========================================================

def end_screen(won):

    waiting = True

    while waiting:

        screen.fill(BLACK)

        if won:

            title_text = "YOU ESCAPED"

            color = GREEN

        else:

            title_text = "IT FOUND YOU"

            color = RED

        title = big_font.render(
            title_text,
            True,
            color
        )

        screen.blit(
            title,
            (
                WIDTH // 2 - title.get_width() // 2,
                HEIGHT // 2 - 80
            )
        )

        restart = font.render(
            "PRESS ENTER TO PLAY AGAIN",
            True,
            WHITE
        )

        screen.blit(
            restart,
            (
                WIDTH // 2 - restart.get_width() // 2,
                HEIGHT // 2 + 40
            )
        )

        pygame.display.flip()

        for event in pygame.event.get():

            if event.type == pygame.QUIT:

                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:

                if event.key == pygame.K_RETURN:
                    waiting = False


# =========================================================
# MAIN GAME
# =========================================================

def main():

    global message_timer
    global game_won
    global game_lost

    title_screen()

    while True:

        reset_game()

        running = True

        while running:

            dt = clock.tick(FPS) / 1000.0

            # Prevent huge movement if game freezes
            dt = min(dt, 0.05)

            # -------------------------------------------------
            # EVENTS
            # -------------------------------------------------

            for event in pygame.event.get():

                if event.type == pygame.QUIT:

                    pygame.quit()
                    sys.exit()

                if event.type == pygame.KEYDOWN:

                    if event.key == pygame.K_ESCAPE:

                        pygame.quit()
                        sys.exit()

                    if event.key == pygame.K_e:

                        interact()

            # -------------------------------------------------
            # TIME
            # -------------------------------------------------

            elapsed = (
                pygame.time.get_ticks()
                - game_start
            ) / 1000

            if elapsed >= GAME_TIME:

                game_lost = True

            # -------------------------------------------------
            # UPDATE
            # -------------------------------------------------

            if not game_won and not game_lost:

                update_player(dt)

                update_creature(
                    dt,
                    elapsed
                )

                update_camera()

                # Escape
                if key_collected:

                    if escape.collidepoint(
                        int(player.x),
                        int(player.y)
                    ):

                        game_won = True

                # Message timer
                if message_timer > 0:

                    message_timer -= dt

                update_audio(elapsed)

            # -------------------------------------------------
            # DRAW
            # -------------------------------------------------

            draw_world()

            draw_creature()

            draw_player()

            draw_darkness(elapsed)

            draw_ui(elapsed)

            pygame.display.flip()

            # -------------------------------------------------
            # END GAME
            # -------------------------------------------------

            if game_won or game_lost:

                running = False

        end_screen(game_won)


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()