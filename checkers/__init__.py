# fmt: off
SQUARES = [
    _, B10, D10, F10, H10, J10,
    A9, C9, E9, G9, I9,
    B8, D8, F8, H8, J8,
    A7, C7, E7, G7, I7,
    B6, D6, F6, H6, J6,
    A5, C5, E5, G5, I5,
    B4, D4, F4, H4, J4,
    A3, C3, E3, G3, I3,
    B2, D2, F2, H2, J2,
    A1, C1, E1, G1, I1
    ] = range(51)

T8X8 = {
        val:idx  for idx,val in enumerate(
        (B8, D8, F8, H8,
        A7, C7, E7, G7,
        B6, D6, F6, H6,
        A5, C5, E5, G5,
        B4, D4, F4, H4,
        A3, C3, E3, G3,
        B2, D2, F2, H2,
        A1, C1, E1, G1) )} 

# fmt: on
T10X10 = {val: idx for idx, val in enumerate(SQUARES)}
