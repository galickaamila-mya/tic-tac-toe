import socket
import threading

HOST = '127.0.0.1'
PORT = 12345

clients = [] # список подключенных клиентов
clients_lock = threading.Lock() # сразу приготовили lock для того, чтобы изменять список АКТИВНЫХ клиентов
games = {}  # словарь для хранения игр: {player_name: {"opponent": opponent_name, "board": [...], "turn": "X"}}

waiting_player = {
    "conn": None,
    "name": None
}

conn_to_name = {}
name_to_conn = {}

conn_to_game = {}
games_lock = threading.Lock()

ROWS = ['A', 'B', 'C']
COLS = ['1', '2', '3']

# функция для отправки сообщения клиенту
def send_message(client, message):
    try:
        client.sendall(message.encode('utf-8'))
    except OSError:
        print(f"[ОШИБКА] Не удалось отправить сообщение клиенту {client}")

def new_board():
    return [[" " for _ in range(3)] for _ in range(3)]

def board_to_server_format(board):
    parts = []
    for r, row in enumerate(board):
        for c, cell in enumerate(row):
            if cell.strip():
                parts.append(f"{ROWS[r]}{COLS[c]}:{cell}")
    return "BOARD " + ("".join(parts) if not parts else ",".join(parts))

def parse_cell(cell):
    if len(cell) != 2:
        return None
    row_ch, col_ch = cell[0].upper(), cell[1]
    if row_ch in ROWS and col_ch in COLS:
        return ROWS.index(row_ch), COLS.index(col_ch)
    return None

def check_win(board, symbol):
    # строки и столбцы
    for i in range(3):
        if all(board[i][j] == symbol for j in range(3)):
            return True
        if all(board[j][i] == symbol for j in range(3)):
            return True
    # диагонали
    if all(board[i][i] == symbol for i in range(3)):
        return True
    if all(board[i][2 - i] == symbol for i in range(3)):
        return True
    return False

def check_draw(board):
    return all(board[r][c].strip() for r in range(3) for c in range(3))

def get_opponent_conn(conn):

    game_id_role = conn_to_game.get(conn)
    if not game_id_role:
        return None
    game_id = game_id_role[0]
    game = games.get(game_id)
    if not game:
        return None
    if game["players"]["X"] == conn:
        return game["players"]["O"]
    return game["players"]["X"]

def get_player_symbol(conn):

    game_id_role = conn_to_game.get(conn)
    if not game_id_role:
        return None
    return game_id_role[1]

def get_game(conn):

    game_id_role = conn_to_game.get(conn)
    if not game_id_role:
        return None
    return games.get(game_id_role[0])

def handle_client(conn, addr):
    print(f"[НОВОЕ ПОДКЛЮЧЕНИЕ] {addr}")
    with clients_lock:
        clients.append(conn)

    player_name = f"Player{addr[1]}"
    conn_to_name[conn] = player_name
    name_to_conn[player_name] = conn

    try:

        with games_lock:
            if waiting_player["conn"] is None:
                waiting_player["conn"] = conn
                waiting_player["name"] = player_name
                send_message(conn, "OPPONENT Ожидание соперника...")
            else:
                # сформировать игру с ожидающим
                p1_conn = waiting_player["conn"]
                p1_name = waiting_player["name"]
                p2_conn = conn
                p2_name = player_name
                waiting_player["conn"] = None
                waiting_player["name"] = None

                game_id = f"{p1_name}_vs_{p2_name}"
                board = new_board()
                games[game_id] = {
                    "players": {"X": p1_conn, "O": p2_conn},
                    "names": {"X": p1_name, "O": p2_name},
                    "board": board,
                    "turn": "X"
                }
                conn_to_game[p1_conn] = (game_id, "X")
                conn_to_game[p2_conn] = (game_id, "O")

                send_message(p1_conn, f"OPPONENT {p2_name}")
                send_message(p2_conn, f"OPPONENT {p1_name}")
                msg_board = board_to_server_format(board)
                send_message(p1_conn, msg_board)
                send_message(p2_conn, msg_board)
                send_message(p1_conn, "TURN X")
                send_message(p2_conn, "TURN X")

        while True:
            data = conn.recv(1024).decode('utf-8')

            if not data:
                print(f"[ОТКЛЮЧЕНИЕ] Клиент {addr} закрыл соединение")
                break

            if data.startswith("MOVE"):
                parts = data.split()
                if len(parts) != 2:
                    send_message(conn, "ERROR Некорректная команда MOVE")
                    continue
                cell = parts[1].strip()
                coords = parse_cell(cell)
                if coords is None:
                    send_message(conn, "ERROR Некорректная клетка")
                    continue
                with games_lock:
                    game = get_game(conn)
                    if not game:
                        send_message(conn, "ERROR Игра не создана")
                        continue
                    my_symbol = get_player_symbol(conn)
                    if not my_symbol:
                        send_message(conn, "ERROR Неизвестный игрок")
                        continue
                    if game["turn"] != my_symbol:
                        send_message(conn, "ERROR Не ваш ход")
                        continue
                    r, c = coords
                    if game["board"][r][c].strip():
                        send_message(conn, "ERROR Клетка занята")
                        continue
                    game["board"][r][c] = my_symbol
                    msg_board = board_to_server_format(game["board"]) 
                    opponent_conn = get_opponent_conn(conn)
                    if check_win(game["board"], my_symbol):
                        send_message(conn, msg_board)
                        send_message(opponent_conn, msg_board)
                        send_message(conn, f"WIN {my_symbol}")
                        send_message(opponent_conn, f"WIN {my_symbol}")
                        gid = conn_to_game[conn][0]
                        games.pop(gid, None)
                        conn_to_game.pop(conn, None)
                        if opponent_conn:
                            conn_to_game.pop(opponent_conn, None)
                        continue
                    if check_draw(game["board"]):
                        send_message(conn, msg_board)
                        send_message(opponent_conn, msg_board)
                        send_message(conn, "DRAW")
                        send_message(opponent_conn, "DRAW")
                        gid = conn_to_game[conn][0]
                        games.pop(gid, None)
                        conn_to_game.pop(conn, None)
                        if opponent_conn:
                            conn_to_game.pop(opponent_conn, None)
                        continue
                    game["turn"] = "O" if game["turn"] == "X" else "X"
                    send_message(conn, msg_board)
                    send_message(opponent_conn, msg_board)
                    send_message(conn, f"TURN {game['turn']}")
                    send_message(opponent_conn, f"TURN {game['turn']}")
            elif data.startswith("CHAT"):
                text = data[4:].strip()
                if not text:
                    send_message(conn, "ERROR Пустое сообщение")
                    continue
                opponent_conn = get_opponent_conn(conn)
                if opponent_conn:
                    send_message(opponent_conn, f"CHAT {conn_to_name.get(conn, 'opponent')}:{text}")
            elif data.startswith("STATUS"):
                with games_lock:
                    game = get_game(conn)
                    if not game:
                        send_message(conn, "ERROR Игра не создана")
                        continue
                    send_message(conn, board_to_server_format(game["board"]))
                    send_message(conn, f"TURN {game['turn']}")
            elif data.lower() == "exit":
                print(f"[ОТКЛЮЧЕНИЕ] Клиент {addr} вышел из игры")
                break
            else:
                send_message(conn, "НЕИЗВЕСТНАЯ КОМАНДА")
    except OSError:
        print(f"[ОТКЛЮЧЕНИЕ] Клиент {addr} отключился некорректно")
    finally:
        with clients_lock:
            if conn in clients:
                clients.remove(conn)
        with games_lock:
            if waiting_player["conn"] == conn:
                waiting_player["conn"] = None
                waiting_player["name"] = None
            game = get_game(conn)
            opponent_conn = get_opponent_conn(conn)
            if game:
                gid = conn_to_game.get(conn, (None,))[0]
                if opponent_conn:
                    send_message(opponent_conn, "CHAT Система: соперник отключился")
                    conn_to_game.pop(opponent_conn, None)
                if gid:
                    games.pop(gid, None)
                conn_to_game.pop(conn, None)
        name = conn_to_name.pop(conn, None)
        if name:
            name_to_conn.pop(name, None)
        conn.close()

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    with server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        print(f"[SERVER RUNNING] {HOST}:{PORT}")
        while True:
            conn, addr = server_socket.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.start()

if __name__ == "__main__":
    start_server()
