import checkers.american as checkers
board = checkers.Board()


board.push_from_str("24-19")
board.push_from_str("12-16")
board.push_from_str("23-18")
print(list(board.legal_moves))
board.push_from_str("16-23")
# board.push_from_str("27-18")
print(board)



# import checkers.base as checkers
# import numpy as np
# CUSTOM_POSITION = np.array([1] * 20 + [-1] * 12, dtype=np.int8)
# board = checkers.BaseBoard(starting_position=CUSTOM_POSITION)
# board.legal_moves = ... # create your own custom legal_moves method (property)
# print(board)
# print(board.legal_moves)
