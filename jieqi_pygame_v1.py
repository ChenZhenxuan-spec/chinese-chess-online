
import tkinter as tk
from tkinter import messagebox
import random
import copy


class ChineseChess:
    def __init__(self, root):
        self.root = root
        self.root.title("中国象棋 - 暗棋与明棋规则模拟")
        self.root.resizable(False, False)

        self.size = 60
        self.margin = 50
        self.selected = None
        self.history = []
        self.captured = []

        self.board_width = self.margin * 2 + 8 * self.size
        self.board_height = self.margin * 2 + 9 * self.size

        # 棋子类型字典
        self.piece_types = {
            "車": "rook", "俥": "rook",
            "馬": "horse", "傌": "horse",
            "象": "elephant", "相": "elephant",
            "士": "advisor", "仕": "advisor",
            "將": "king", "帥": "king",
            "砲": "cannon", "炮": "cannon",
            "卒": "pawn", "兵": "pawn"
        }

        self.create_ui()
        self.reset_pieces()
        self.draw()
    
    def draw_captured_pieces(self, canvas, pieces, color):
        """图形化绘制已被吃棋子"""

        canvas.delete("all")

        # 每行4枚棋子
        columns = 4
        spacing = 52
        radius = 20

        text_color = (
            "#C52222" if color == "red" else "#222222"
        )

        for i, piece in enumerate(pieces):
            row = i // columns
            col = i % columns

            x = 32 + col * spacing
            y = 30 + row * spacing

            # 棋子主体
            canvas.create_oval(
                x-radius, y-radius,
                x+radius, y+radius,
                fill="#F9E4BC",
                outline="#654321",
                width=2
            )

            # 棋子内圈装饰
            canvas.create_oval(
                x-radius+4, y-radius+4,
                x+radius-4, y+radius-4,
                outline="#AD8956",
                width=1
            )

            # 显示真实身份
            canvas.create_text(
                x, y,
                text=piece["name"],
                fill=text_color,
                font=("楷体", 21, "bold")
            )

    def create_ui(self):
        main_frame = tk.Frame(self.root)
        main_frame.pack(padx=10, pady=10)

        self.canvas = tk.Canvas(
            main_frame,
            width=self.board_width,
            height=self.board_height,
            bg="#EAC48A",
            highlightthickness=0
        )
        self.canvas.pack(side=tk.LEFT)


        # 右侧图形化吃子区域
        side = tk.Frame(main_frame, width=230)
        side.pack(side=tk.RIGHT, fill=tk.Y, padx=15)

        tk.Label(
            side,
            text="已被吃棋子",
            font=("微软雅黑", 15, "bold")
        ).pack(pady=(10, 20))

        # 红方被吃棋子
        self.red_title = tk.Label(
            side,
            text="红方已被吃（0）",
            fg="#C52222",
            font=("微软雅黑", 12, "bold")
        )
        self.red_title.pack(anchor="w", pady=5)

        self.red_captured_canvas = tk.Canvas(
            side,
            width=220,
            height=200,
            bg="#EAC48A",
            highlightthickness=0
        )
        self.red_captured_canvas.pack()

        # 黑方被吃棋子
        self.black_title = tk.Label(
            side,
            text="黑方已被吃（0）",
            fg="#222222",
            font=("微软雅黑", 12, "bold")
        )
        self.black_title.pack(anchor="w", pady=(20, 5))

        self.black_captured_canvas = tk.Canvas(
            side,
            width=220,
            height=200,
            bg="#EAC48A",
            highlightthickness=0
        )
        self.black_captured_canvas.pack()


        self.status_label = tk.Label(
            self.root,
            text="请选择棋子",
            font=("微软雅黑", 11)
        )
        self.status_label.pack(pady=5)

        buttons = tk.Frame(self.root)
        buttons.pack(pady=8)

        tk.Button(
            buttons,
            text="返回上一步",
            font=("微软雅黑", 12),
            width=13,
            command=self.undo
        ).pack(side=tk.LEFT, padx=8)

        tk.Button(
            buttons,
            text="重新开始",
            font=("微软雅黑", 12),
            width=13,
            command=self.restart
        ).pack(side=tk.LEFT, padx=8)

        self.canvas.bind("<Button-1>", self.on_click)

    def reset_pieces(self):
        """混合随机分配30枚暗棋"""

        self.pieces = {}
        self.history = []
        self.captured = []
        self.selected = None

        black_names = [
            "車", "馬", "象", "士",
            "士", "象", "馬", "車",
            "砲", "砲",
            "卒", "卒", "卒", "卒", "卒"
        ]

        red_names = [
            "俥", "傌", "相", "仕",
            "仕", "相", "傌", "俥",
            "炮", "炮",
            "兵", "兵", "兵", "兵", "兵"
        ]

        all_pieces = []

        for name in black_names:
            all_pieces.append({
                "name": name,
                "color": "black",
                "revealed": False
            })

        for name in red_names:
            all_pieces.append({
                "name": name,
                "color": "red",
                "revealed": False
            })

        random.shuffle(all_pieces)

        # 将帅固定明牌
        self.pieces[(0, 4)] = {
            "name": "將",
            "color": "black",
            "revealed": True,
            "hidden_type": "king",
            "hidden_side": "black"
        }

        self.pieces[(9, 4)] = {
            "name": "帥",
            "color": "red",
            "revealed": True,
            "hidden_type": "king",
            "hidden_side": "red"
        }

        # 原位置的棋子类型
        # 格式：行、列、原本应该是什么棋子
        initial_positions = []

        back_row = [
            "rook", "horse", "elephant", "advisor",
            "king", "advisor", "elephant", "horse", "rook"
        ]

        for col in range(9):
            if col != 4:
                initial_positions.append(
                    (0, col, back_row[col], "black")
                )
                initial_positions.append(
                    (9, col, back_row[col], "red")
                )

        for col in [1, 7]:
            initial_positions.append(
                (2, col, "cannon", "black")
            )
            initial_positions.append(
                (7, col, "cannon", "red")
            )

        for col in [0, 2, 4, 6, 8]:
            initial_positions.append(
                (3, col, "pawn", "black")
            )
            initial_positions.append(
                (6, col, "pawn", "red")
            )

        # 将随机棋子依次分配到30个位置
        for (row, col, hidden_type, hidden_side), piece in zip(
            initial_positions, all_pieces
        ):
            piece["hidden_type"] = hidden_type
            piece["hidden_side"] = hidden_side
            self.pieces[(row, col)] = piece

        self.update_captured()
        self.status_label.config(text="新棋局：请点击棋子")

    def point(self, row, col):
        return (
            self.margin + col * self.size,
            self.margin + row * self.size
        )

    def draw_board(self):
        c = self.canvas
        c.delete("all")

        left = self.margin
        right = left + 8 * self.size
        top = self.margin
        bottom = top + 9 * self.size

        for row in range(10):
            y = top + row * self.size
            c.create_line(left, y, right, y, width=2)

        for col in range(9):
            x = left + col * self.size

            if col in (0, 8):
                c.create_line(x, top, x, bottom, width=2)
            else:
                c.create_line(
                    x, top, x,
                    top + 4 * self.size, width=2
                )
                c.create_line(
                    x, top + 5 * self.size,
                    x, bottom, width=2
                )

        for row in [0, 7]:
            x1, y1 = self.point(row, 3)
            x2, y2 = self.point(row + 2, 5)
            c.create_line(x1, y1, x2, y2, width=2)

            x3, y3 = self.point(row, 5)
            x4, y4 = self.point(row + 2, 3)
            c.create_line(x3, y3, x4, y4, width=2)

        c.create_text(
            left + 2 * self.size,
            top + 4.5 * self.size,
            text="楚 河",
            font=("楷体", 25, "bold")
        )

        c.create_text(
            left + 6 * self.size,
            top + 4.5 * self.size,
            text="漢 界",
            font=("楷体", 25, "bold")
        )

    def get_active_type(self, piece):
        """判断棋子当前按哪种身份行走"""

        if piece["revealed"]:
            # 明棋按真实身份
            return self.piece_types[piece["name"]]
        else:
            # 暗棋按原始位置身份
            return piece["hidden_type"]

    def get_active_side(self, piece):
        """暗棋按位置阵营，明棋按真实阵营"""

        if piece["revealed"]:
            return piece["color"]
        return piece["hidden_side"]

    def in_palace(self, row, col, side):
        """判断是否在所属九宫格"""

        if not (3 <= col <= 5):
            return False

        if side == "black":
            return 0 <= row <= 2

        return 7 <= row <= 9

    def crossed_river(self, row, side):
        """判断是否过河"""

        if side == "black":
            return row >= 5
        return row <= 4

    def count_between(self, start, end):
        """统计两个位置之间的阻挡棋子数量"""

        r1, c1 = start
        r2, c2 = end

        count = 0

        if r1 == r2:
            step = 1 if c2 > c1 else -1

            for c in range(c1 + step, c2, step):
                if (r1, c) in self.pieces:
                    count += 1

        elif c1 == c2:
            step = 1 if r2 > r1 else -1

            for r in range(r1 + step, r2, step):
                if (r, c1) in self.pieces:
                    count += 1

        return count

    def is_valid_move(self, start, end):
        """按照当前身份判断走法是否合法"""

        if start not in self.pieces:
            return False

        if start == end:
            return False

        piece = self.pieces[start]

        piece_type = self.get_active_type(piece)
        side = self.get_active_side(piece)

        r1, c1 = start
        r2, c2 = end

        dr = r2 - r1
        dc = c2 - c1

        ar = abs(dr)
        ac = abs(dc)

        target_occupied = end in self.pieces

        # 1. 車：横竖直线，中间不能有棋子
        if piece_type == "rook":

            if r1 != r2 and c1 != c2:
                return False

            return self.count_between(start, end) == 0

        # 2. 馬：走日，不能蹩马腿
        elif piece_type == "horse":

            if (ar, ac) not in [(2, 1), (1, 2)]:
                return False

            if ar == 2:
                leg = (r1 + dr // 2, c1)
            else:
                leg = (r1, c1 + dc // 2)

            return leg not in self.pieces

         # 3. 象/相：走田，可以过河，但不能塞象眼
        elif piece_type == "elephant":

            if ar != 2 or ac != 2:
                return False

            # 判断象眼是否被堵住
            eye = (r1 + dr // 2, c1 + dc // 2)

            if eye in self.pieces:
                return False

            return True

        # 4. 士/仕：斜走一格，不限制九宫格
        elif piece_type == "advisor":

            if ar == 1 and ac == 1:
                return True

            return False

        # 5. 将/帅：九宫格内直走一步
        elif piece_type == "king":

            # 飞将：允许同列无阻挡时直接吃对方将帅
            if target_occupied:
                target = self.pieces[end]

                if (
                    self.get_active_type(target) == "king"
                    and target["color"] != piece["color"]
                    and c1 == c2
                    and self.count_between(start, end) == 0
                ):
                    return True

            if ar + ac != 1:
                return False

            return self.in_palace(r2, c2, side)

        # 6. 炮：不吃子无炮架，吃子必须恰好一个炮架
        elif piece_type == "cannon":

            if r1 != r2 and c1 != c2:
                return False

            between = self.count_between(start, end)

            if target_occupied:
                return between == 1
            else:
                return between == 0

        # 7. 兵/卒：过河前只能向前，过河后可以横走
        elif piece_type == "pawn":

            forward = 1 if side == "black" else -1

            # 向前一步
            if dr == forward and dc == 0:
                return True

            # 过河后可以左右一步
            if self.crossed_river(r1, side):
                if dr == 0 and ac == 1:
                    return True

            return False

        return False

    def get_legal_moves(self, start):
        """获得该棋子所有合法目标位置"""

        legal_moves = []

        for row in range(10):
            for col in range(9):

                end = (row, col)

                if self.is_valid_move(start, end):
                    legal_moves.append(end)

        return legal_moves

    def draw_pieces(self):
        """绘制棋子与选中状态"""

        for (row, col), piece in self.pieces.items():

            x, y = self.point(row, col)
            r = 25

            selected = self.selected == (row, col)

            outline = "#E5A000" if selected else "#654321"
            width = 4 if selected else 2

            self.canvas.create_oval(
                x-r, y-r, x+r, y+r,
                fill="#F9E4BC",
                outline=outline,
                width=width
            )

            # 暗棋不显示文字
            if piece["revealed"]:

                color = (
                    "#C52222"
                    if piece["color"] == "red"
                    else "#222222"
                )

                self.canvas.create_text(
                    x, y,
                    text=piece["name"],
                    fill=color,
                    font=("楷体", 26, "bold")
                )

    def draw_legal_moves(self):
        """显示选中棋子的合法落点"""

        if self.selected is None:
            return

        moves = self.get_legal_moves(self.selected)

        for row, col in moves:

            x, y = self.point(row, col)

            if (row, col) in self.pieces:

                # 可以吃子：用绿色外圈标注
                self.canvas.create_oval(
                    x-29, y-29,
                    x+29, y+29,
                    outline="#259447",
                    width=3
                )

            else:

                # 空位置：用绿色小圆点标注
                self.canvas.create_oval(
                    x-6, y-6,
                    x+6, y+6,
                    fill="#259447",
                    outline=""
                )

    def draw(self):
        self.draw_board()
        self.draw_pieces()
        self.draw_legal_moves()

    def on_click(self, event):
        """处理鼠标点击"""

        col = round(
            (event.x - self.margin) / self.size
        )
        row = round(
            (event.y - self.margin) / self.size
        )

        if not (0 <= row <= 9 and 0 <= col <= 8):
            return

        x, y = self.point(row, col)

        if abs(event.x - x) > 27:
            return

        if abs(event.y - y) > 27:
            return

        target = (row, col)

        # 没选棋子时，点击选择
        if self.selected is None:

            if target in self.pieces:
                self.selected = target
                self.show_selected_info(target)

        else:

            # 点击已选棋子，取消选中
            if target == self.selected:

                self.selected = None
                self.status_label.config(
                    text="已取消选择"
                )

            # 合法落点：执行移动
            elif self.is_valid_move(self.selected, target):

                self.move_piece(self.selected, target)
                self.selected = None

            else:

                # 如果点到其他棋子，允许切换选择
                if target in self.pieces:
                    self.selected = target
                    self.show_selected_info(target)

                else:
                    self.status_label.config(
                        text="不符合当前棋子的行棋规则"
                    )

        self.draw()

    def show_selected_info(self, pos):
        """显示当前棋子采用的走法"""

        piece = self.pieces[pos]

        type_names = {
            "rook": "車",
            "horse": "馬",
            "elephant": "象",
            "advisor": "士",
            "king": "将帅",
            "cannon": "炮",
            "pawn": "兵卒"
        }

        current_type = self.get_active_type(piece)
        name = type_names[current_type]

        if piece["revealed"]:

            info = (
                f"当前明棋：{piece['name']}，"
                f"按照{name}的规则移动"
            )

        else:

            info = (
                f"当前暗棋：按照初始位置的{name}走法移动"
            )

        self.status_label.config(text=info)

    def move_piece(self, start, end):
        """执行移动、吃子和翻牌"""

        if not self.is_valid_move(start, end):
            return

        self.history.append({
            "pieces": copy.deepcopy(self.pieces),
            "captured": copy.deepcopy(self.captured)
        })

        # 如果目标位置有棋子，则吃掉
        if end in self.pieces:

            captured_piece = copy.deepcopy(self.pieces[end])

            # 被吃的棋子公开真实身份
            captured_piece["revealed"] = True

            self.captured.append(captured_piece)

        # 移动
        moving_piece = self.pieces.pop(start)

        # 无论之前是否为暗棋，移动后都保持明牌
        moving_piece["revealed"] = True

        self.pieces[end] = moving_piece

        self.update_captured()

        self.status_label.config(
            text=f"移动成功：{moving_piece['name']}"
        )

    
    def update_captured(self):
        """刷新图形化吃子展示区域"""

        red_pieces = [
            p for p in self.captured
            if p["color"] == "red"
        ]

        black_pieces = [
            p for p in self.captured
            if p["color"] == "black"
        ]

        # 更新数量
        self.red_title.config(
            text=f"红方已被吃（{len(red_pieces)}）"
        )

        self.black_title.config(
            text=f"黑方已被吃（{len(black_pieces)}）"
        )

        # 绘制棋子
        self.draw_captured_pieces(
            self.red_captured_canvas,
            red_pieces,
            "red"
        )

        self.draw_captured_pieces(
            self.black_captured_canvas,
            black_pieces,
            "black"
        )


    def undo(self):
        """撤销一步，恢复明暗状态"""

        if not self.history:

            self.status_label.config(
                text="已经是最初状态"
            )
            return

        previous = self.history.pop()

        self.pieces = previous["pieces"]
        self.captured = previous["captured"]

        self.selected = None

        self.update_captured()
        self.draw()

        self.status_label.config(
            text="已返回上一步"
        )

    def restart(self):
        """重开新局并重新洗牌"""

        result = messagebox.askyesno(
            "重新开始",
            "确定重新洗牌并开始新棋局吗？"
        )

        if result:
            self.reset_pieces()
            self.draw()


if __name__ == "__main__":
    root = tk.Tk()
    app = ChineseChess(root)
    root.mainloop()
