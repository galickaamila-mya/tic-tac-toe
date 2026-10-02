import socket
import threading
import re

# у нас будет два потока:
# первый поток (наш основной поток) - ввода команд пользователем
# второй поток (мы его создали дополнительно) - прием сообщений от сервера и отображение доски, чата и результатов игры

HOST = '127.0.0.1'
PORT = 12345

ROWS = ['A', 'B', 'C']
COLS = ['1', '2', '3']

def parse_board_payload(payload: str, state: dict):
    board = state['board']
    for r in range(3):
        for c in range(3):
            board[r][c] = ' '
    payload = payload.strip()
    if not payload:
        return
    parts = payload.split(',')
    for part in parts:
        part = part.strip()
        if not part or ':' not in part:
            continue
        cell, sym = part.split(':', 1)
        cell = cell.strip()
        sym = sym.strip()
        if len(cell) == 2 and cell[0] in ROWS and cell[1] in COLS and sym in ('X', 'O'):
            r = ROWS.index(cell[0])
            c = COLS.index(cell[1])
            board[r][c] = sym

def render_board(state: dict):
    board = state['board']
    turn = state['turn']
    opponent = state['opponent']
    lines = []
    lines.append("\n╔═══════════════════╗")
    lines.append("║  КРЕСТИКИ-НОЛИКИ  ║")
    lines.append("╠═══════════════════╣")
    lines.append("║     1   2   3     ║")
    lines.append("║   ┌───┬───┬───┐   ║")
    for ri, row in enumerate(board):
        row_label = ROWS[ri]
        lines.append(f"║ {row_label} │ {row[0]} │ {row[1]} │ {row[2]} │   ║")
        if ri < 2:
            lines.append("║   ├───┼───┼───┤   ║")
    lines.append("║   └───┴───┴───┘   ║")
    turn_str = turn if turn in ('X', 'O') else '?'
    lines.append("║                   ║")
    lines.append(f"║ Ход: {turn_str}           ║")
    if opponent:
        lines.append(f"║ Соперник: {opponent} ║")
    lines.append("╚═══════════════════╝")
    print("\n".join(lines))

def receive_messages(sock):
    state = {
        'board': [[' ' for _ in range(3)] for _ in range(3)],
        'turn': None,
        'opponent': None,
    }

    while True:
        try:
            data = sock.recv(1024).decode('utf-8')
            if not data:
                print("[ОТКЛЮЧЕНИЕ] Сервер закрыл соединение")
                break

            msg = data.strip()

            if msg.startswith('BOARD'):
                payload = msg[5:].strip()
                if payload.startswith(' '):
                    payload = payload[1:]
                parse_board_payload(payload, state)
                render_board(state)
            elif msg.startswith('TURN'):
                parts = msg.split()
                if len(parts) == 2:
                    state['turn'] = parts[1]
                render_board(state)
            elif msg.startswith('CHAT'):
                text = msg[4:].strip()
                print(f"\n[ЧАТ] {text}")
            elif msg.startswith('WIN'):
                print(f"\n[ИТОГ] {msg}")
            elif msg.startswith('DRAW'):
                print("\n[ИТОГ] Ничья")
            elif msg.startswith('OPPONENT'):
                state['opponent'] = msg[8:].strip()
                print(f"\n[СОПЕРНИК] {state['opponent']}")
            else:
                print("\n[СЕРВЕР]:", msg)

            print("Введите команду: ", end="")

        except OSError:
            print("[ОТКЛЮЧЕНИЕ] Соединение разорвано сервером")
            break


def start_client():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with client_socket:
        client_socket.connect((HOST, PORT))
        print("[ПОДКЛЮЧЕНИЕ] Подключено к серверу")

        threading.Thread(target=receive_messages, args=(client_socket,), daemon=True).start()

        while True:
            command = input("Введите команду (A1/B2..., chat <msg>, status, exit): ").strip()
            if command.lower() == "exit":
                client_socket.sendall("exit".encode('utf-8'))
                print("[ВЫХОД] Вы отключились от сервера")
                break

            normalized = command
            if re.fullmatch(r"[abcABC][123]", command):
                normalized = f"MOVE {command.upper()}"
            elif command.lower().startswith("move "):
                cell = command[5:].strip().upper()
                if re.fullmatch(r"[ABC][123]", cell):
                    normalized = f"MOVE {cell}"
                else:
                    print("[ОШИБКА] Неверная клетка. Используйте форматы A1..C3")
                    continue
            elif command.lower().startswith("chat "):
                text = command[5:].strip()
                if not text:
                    print("[ОШИБКА] Пустое сообщение чата")
                    continue
                normalized = f"CHAT {text}"
            elif command.lower() == "status":
                normalized = "STATUS"

            client_socket.sendall(normalized.encode('utf-8'))

if __name__ == "__main__":
    start_client()
