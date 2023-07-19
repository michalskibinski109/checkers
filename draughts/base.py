from __future__ import annotations

import re
from abc import ABC, abstractproperty
from typing import Generator

import numpy as np

from draughts.models import FIGURE_REPR, Color, Figure, SquareT
from draughts.move import Move
from draughts.utils import logger

# fmt: off
SQUARES = [_, B8, D8, F8, H8,
        A7, C7, E7, G7,
        B6, D6, F6, H6,
        A5, C5, E5, G5,
        B4, D4, F4, H4,
        A3, C3, E3, G3,
        B2, D2, F2, H2,
        A1, C1, E1, G1] = range(33)
# fmt: on


class BaseBoard(ABC):
    """
    Abstact class for all draughts variants.

    .. important::
        All boards contain all methods from this class.

    Class is designed to support draughts boards of any size.
    By specifying the starting position, the user can create a board of any size.



    To create new variants of draughts, inherit from this class and:

    - override the ``legal_moves`` property
    - override the ``SQUARES`` list to match the new board size
    - override the ``STARTING_POSITION`` to specify the starting position

    Constraints:
    - There are only two colors:
        - ``Color.WHITE``
        - ``Color.BLACK``

    - There are only two types of pieces:
        - ``PieceType.MAN``
        - ``PieceType.KING``
    - **Board should always be square.**
    """

    GAME_TYPE = -1
    """
    PDN game type. See `PDN specification <https://en.wikipedia.org/wiki/Portable_Draughts_Notation>`_.
    """
    VARIANT_NAME = "Abstract variant"
    STARTING_POSITION = np.array([1] * 12 + [0] * 8 + [-1] * 12, dtype=np.int8)
    ROW_IDX = ...
    """ 
    Dictionary of row indexes for every square. Generated only on module import. 
    Used to calculate legal moves.
    """

    COL_IDX = ...
    """
    Same as ``ROW_IDX`` but for columns.
    """

    STARTING_COLOR = Color.WHITE
    """
    Starting color. ``Color.WHITE`` or ``Color.BLACK``.
    """

    PSEUDO_LEGAL_KING_MOVES = None
    """
    Dictionary of pseudo-legal moves for king pieces. Generated only on module import.
    This dictionary contains all possible moves for king piece (as if there were no other pieces on the board).
    
    **Structure:**
    
    ``[(right-up moves), (left-up moves), (right-down moves), (left-down moves)]``
    
    """
    PSEUDO_LEGAL_MAN_MOVES = None
    """ 
    Same as ``PSEUDO_LEGAL_KING_MOVES`` but contains only first 2 squares of the move.
    (one for move and one for capture)
    """

    def __init__(self, starting_position: np.ndarray) -> None:
        """
        Initializes the board with a starting position.
        The starting position must be a numpy array of length n * n/2,
        where n is the size of the board.

        """
        super().__init__()
        self._pos = starting_position.copy()
        self.turn = self.STARTING_COLOR
        size = int(np.sqrt(len(self.position) * 2))
        if size**2 != len(self.position) * 2:
            msg = f"Invalid board with shape {starting_position.shape} provided.\
                Please use an array with lenght = (n * n/2). \
                Where n is an size of the board."
            logger.error(msg)
            raise ValueError(msg)
        self.shape = (size, size)
        self._moves_stack: list[Move] = []
        logger.info(f"Board initialized with shape {self.shape}.")

    # @abstractmethod
    @property
    def legal_moves(self) -> Generator[Move, None, None]:
        """
        Return list legal moves for the current position.
        *For every concrete variant of draughts this method should be overriden.*

        .. warning::
            Depending of implementation method can return generator or list.


        """
        pass

    @property
    def position(self) -> np.ndarray:
        """Returns board position."""
        return self._pos

    @property
    def is_threefold_repetition(self) -> bool:
        if len(self._moves_stack) >= 9:
            if (
                self._moves_stack[-1].square_list
                == self._moves_stack[-5].square_list
                == self._moves_stack[-9].square_list
            ):
                return True
        return False

    @property
    def is_draw(self) -> bool:
        raise NotImplementedError

    @property
    def game_over(self) -> bool:
        """Returns ``True`` if the game is over."""
        # check if threefold repetition

        return self.is_draw or not bool(list(self.legal_moves))

    def push(
        self, move: Move, is_finished: bool = True
    ) -> None:  # TODO multiple captures != promotion
        """Pushes a move to the board.
        Automatically promotes a piece if it reaches the last row.

        If ``is_finished`` is set to ``True``, the turn is switched. This parameter is used only
        for generating legal moves.
        """
        src, tg = (
            move.square_list[0],
            move.square_list[-1],
        )
        self._pos[src], self._pos[tg] = self._pos[tg], self._pos[src]
        # is promotion
        if (
            (tg // (self.shape[0] // 2)) == 0
            and self._pos[tg] == Figure.WHITE_MAN.value
        ) or (
            (tg // (self.shape[0] // 2)) == (self.shape[0] - 1)
            and self._pos[tg] == Figure.BLACK_MAN.value
        ):
            self._pos[tg] *= Figure.KING.value
            move.is_promotion = True
        if move.captured_list:
            self._pos[np.array([sq for sq in move.captured_list])] = Figure.EMPTY
        self._moves_stack.append(move)
        if is_finished:
            self.turn = Color.WHITE if self.turn == Color.BLACK else Color.BLACK

    def pop(self, is_finished=True) -> None:
        """Pops a move from the board.

        If ``is_finished`` is set to ``True``, the turn is switched. This parameter is used only
        for generating legal moves.
        """
        move = self._moves_stack.pop()
        src, tg = (
            move.square_list[0],
            move.square_list[-1],
        )
        if move.is_promotion:
            self._pos[tg] //= Figure.KING.value
        self._pos[src], self._pos[tg] = self._pos[tg], self._pos[src]
        for sq, entity in zip(move.captured_list, move.captured_entities):
            self._pos[sq] = entity  # Dangerous line
        if is_finished:
            self.turn = Color.WHITE if self.turn == Color.BLACK else Color.BLACK
        return move

    def push_uci(self, str_move: str) -> None:
        """
        Allows to push a move from a string.

        * Converts string to ``Move`` object
        * calls ``BaseBoard.push`` method
        """
        try:
            move = Move.from_uci(str_move, self.legal_moves)
        except ValueError as e:
            logger.error(f"{e} \n {str(self)}")
            raise e
        self.push(move)

    @property
    def fen(self):
        """
        Returns a FEN string of the board position.

        ``[FEN "[Turn]:[Color 1][K][Square number][,]...]:[Color 2][K][Square number][,]...]"]``

        Fen examples:

        - ``[FEN "B:W18,24,27,28,K10,K15:B12,16,20,K22,K25,K29"]``
        - ``[FEN "B:W18,19,21,23,24,26,29,30,31,32:B1,2,3,4,6,7,9,10,11,12"]``
        """
        COLORS_REPR = {Color.WHITE: "W", Color.BLACK: "B"}
        fen_components = [
            f'[FEN "W:{COLORS_REPR[self.turn]}:W',
            ",".join(
                "K" * bool(self._pos[sq] < -1) + str(sq + 1)
                for sq in np.where(self.position < 0)[0]
            ),
            ":B",
            ",".join(
                "K" * bool(self._pos[sq] > 1) + str(sq + 1)
                for sq in np.where(self.position > 0)[0]
            ),
            '"]',
        ]
        return "".join(fen_components)

    @classmethod
    def from_fen(cls, fen: str) -> BaseBoard:
        """
        Creates a board from a FEN string by using regular expressions.
        """
        fen = fen.upper()
        re_turn = re.compile(r"[WB]:")
        re_premove = re.compile(r"(G[0-9]+|P[0-9]+)(,|)")
        re_prefix = re.compile(r"[WB]:[WB]:[WB]")
        re_white = re.compile(r"W[0-9K,]+")
        re_black = re.compile(r"B[0-9K,]+")
        # remove premoves from fen
        # remove first 2 letters from prefix
        fen = re_premove.sub("", fen)
        prefix = re_prefix.search(fen)
        if prefix:
            prefix = prefix.group(0)
            fen = fen.replace(prefix, prefix[2:])
        try:
            turn = re_turn.search(fen).group(0)[0]
            white = re_white.search(fen).group(0).replace("W", "")
            black = re_black.search(fen).group(0).replace("B", "")
        except AttributeError as e:
            raise AttributeError(f"Invalid FEN: {fen} \n {e}")
        logger.debug(f"turn: {turn}, white: {white}, black: {black}")
        cls.STARTING_POSITION = np.zeros(cls.STARTING_POSITION.shape, dtype=np.int8)
        if len(turn) != 1 or (len(white) == 0 and len(black) == 0):
            raise ValueError(f"Invalid FEN: {fen}")
        try:
            cls.__populate_from_list(white.split(","), Color.WHITE)
            cls.__populate_from_list(black.split(","), Color.BLACK)
        except ValueError as e:
            logger.error(f"Invalid FEN: {fen} \n {e}")
        cls.turn = Color.WHITE if turn == "W" else Color.BLACK
        cls.STARTING_COLOR = cls.turn
        return cls(starting_position=cls.STARTING_POSITION)

    @classmethod
    def __populate_from_list(cls, fen_list: list[str], color: Color) -> None:
        board_range = range(1, cls.STARTING_POSITION.shape[0] + 1)
        for sq in fen_list:
            if sq.isdigit() and int(sq) in board_range:
                cls.STARTING_POSITION[int(sq) - 1] = color.value
            elif sq.startswith("K") and sq[1:].isdigit() and int(sq[1:]) in board_range:
                cls.STARTING_POSITION[int(sq[1:]) - 1] = color.value * Figure.KING.value
            else:
                raise ValueError(
                    f"invalid square value: {sq} for board with length\
                        {cls.STARTING_POSITION.shape[0]}"
                )

    @classmethod
    @property
    def info(cls) -> str:
        board_size = int(np.sqrt(cls.STARTING_POSITION.shape[0]))
        data = (
            f'[GameType "{cls.GAME_TYPE}"]\n'
            f'[Variant "{cls.VARIANT_NAME}"]\n'
            f'[BoardSize "{board_size} X {board_size}"]\n'
            f'[StartingColor "{cls.STARTING_COLOR}"]\n'
        )
        return data

    @property
    def friendly_form(self) -> np.ndarray:
        """
        Returns a board position in a friendly form.
        *Makes board with size n x n from a board with size n x n/2*
        """
        new_pos = [0]
        for idx, sq in enumerate(self.position):
            new_pos.extend([0] * (idx % (self.shape[0] // 2) != 0))
            new_pos.extend([0, 0] * (idx % self.shape[0] == 0 and idx != 0))
            new_pos.append(sq)
        new_pos.append(0)
        return np.array(new_pos)

    @staticmethod
    def is_capture(move: Move) -> bool:
        """
        Checks if a move is a capture.
        """
        return len(move.captured_list) > 0

    def __repr__(self) -> str:
        board = ""
        position = self.friendly_form
        for i in range(self.shape[0]):
            # board += f"{'-' * (self.shape[0]*4 + 1) }\n|"
            for j in range(self.shape[0]):
                board += f" {FIGURE_REPR[position[i*self.shape[0] + j]]}"
            board += "\n"
        return board

    def __iter__(self) -> Generator[Figure, None, None]:
        for sq in self.position:
            yield sq

    def __getitem__(self, key: SquareT) -> Figure:
        return self.position[key]


if __name__ == "__main__":
    board = BaseBoard(BaseBoard.STARTING_POSITION)
    # print(board)
# print(board.info)
#     m1 = Move([C3, B4])
#     board.push(m1)

#     m2 = Move([B6, A5])
#     board.push(m2)

#     m3 = Move([G3, H4])
#     board.push(m3)
#     print(board)

#     m4 = Move([A5, C3], captured_list=[B4])
#     board.push(m4)
#     print(board)
