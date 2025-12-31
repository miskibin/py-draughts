"""
SVG rendering for draughts boards.

Renders draughts boards as SVG images with support for:
- 8×8 (American) and 10×10 (Standard/Frisian) board variants
- Piece rendering (men and kings)
- Move highlighting
- Arrows and square annotations
- Coordinate labels
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from typing import Dict, Iterable, List, Optional, Tuple, Union

from draughts.models import Color, Figure
from draughts.move import Move

# Constants
SQUARE_SIZE = 45
MARGIN = 20

# Default colors matching the web interface
DEFAULT_COLORS = {
    "square light": "#e8d4b8",
    "square dark": "#b58863",
    "square dark lastmove": "#aaa23b",
    "square light lastmove": "#cdd16a",
    "margin": "#212121",
    "coord": "#e5e5e5",
    "arrow green": "#15781B80",
    "arrow red": "#88202080",
    "arrow yellow": "#e68f00b3",
    "arrow blue": "#00308880",
    "piece white": "#f0f0f0",
    "piece black": "#1a1a1a",
    "piece white stroke": "#000000",
    "piece black stroke": "#000000",
    "crown white": "#c4a000",
    "crown black": "#ffd700",
}

# Crown SVG path for king pieces
CROWN_PATH = "M 5,10 L 8,4 L 11,8 L 14,2 L 17,8 L 20,4 L 23,10 L 21,10 L 21,16 L 7,16 L 7,10 Z"


class Arrow:
    """Details of an arrow to be drawn."""

    tail: int
    """Start square of the arrow (0-indexed)."""

    head: int
    """End square of the arrow (0-indexed)."""

    color: str
    """Arrow color."""

    def __init__(self, tail: int, head: int, *, color: str = "green") -> None:
        self.tail = tail
        self.head = head
        self.color = color

    def __repr__(self) -> str:
        return f"Arrow({self.tail}, {self.head}, color={self.color!r})"


class SvgWrapper(str):
    """Wrapper for SVG strings that provides Jupyter notebook integration."""

    def _repr_svg_(self) -> SvgWrapper:
        return self

    def _repr_html_(self) -> SvgWrapper:
        return self


def _svg(viewbox: int, size: Optional[int]) -> ET.Element:
    """Create the root SVG element."""
    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "xmlns:xlink": "http://www.w3.org/1999/xlink",
            "viewBox": f"0 0 {viewbox:d} {viewbox:d}",
        },
    )

    if size is not None:
        svg.set("width", str(size))
        svg.set("height", str(size))

    return svg


def _attrs(attrs: Dict[str, Union[str, int, float, None]]) -> Dict[str, str]:
    """Filter out None values and convert to strings."""
    return {k: str(v) for k, v in attrs.items() if v is not None}


def _color(color: str) -> Tuple[str, float]:
    """Parse a color string, extracting opacity if present."""
    if color.startswith("#"):
        try:
            if len(color) == 5:
                return color[:4], int(color[4], 16) / 0xF
            elif len(color) == 9:
                return color[:7], int(color[7:], 16) / 0xFF
        except ValueError:
            pass
    return color, 1.0


def _select_color(colors: Dict[str, str], color: str) -> Tuple[str, float]:
    """Select a color from the colors dict or default colors."""
    return _color(colors.get(color, DEFAULT_COLORS.get(color, "#000000")))


def _get_square_center(
    square_idx: int,
    board_size: int,
    orientation: Color,
    board_offset: int,
) -> Tuple[float, float]:
    """
    Calculate the center coordinates of a playable square.

    Args:
        square_idx: 0-indexed playable square number
        board_size: Board dimension (8 or 10)
        orientation: Viewing orientation
        board_offset: Offset from SVG edge to board

    Returns:
        Tuple of (x, y) center coordinates
    """
    squares_per_row = board_size // 2

    row = square_idx // squares_per_row
    col_in_row = square_idx % squares_per_row

    # Dark squares alternate: even rows start at col 1, odd rows at col 0
    if row % 2 == 0:
        col = col_in_row * 2 + 1
    else:
        col = col_in_row * 2

    # Apply orientation
    if orientation == Color.WHITE:
        x = col * SQUARE_SIZE + SQUARE_SIZE / 2 + board_offset
        y = row * SQUARE_SIZE + SQUARE_SIZE / 2 + board_offset
    else:
        x = (board_size - 1 - col) * SQUARE_SIZE + SQUARE_SIZE / 2 + board_offset
        y = (board_size - 1 - row) * SQUARE_SIZE + SQUARE_SIZE / 2 + board_offset

    return x, y


def _render_piece(
    svg: ET.Element,
    piece_value: int,
    x: float,
    y: float,
    colors: Dict[str, str],
) -> None:
    """Render a piece at the given coordinates."""
    is_white = piece_value < 0
    is_king = abs(piece_value) == 2

    # Select colors
    if is_white:
        fill_color, fill_opacity = _select_color(colors, "piece white")
        stroke_color, stroke_opacity = _select_color(colors, "piece white stroke")
        crown_color, crown_opacity = _select_color(colors, "crown white")
    else:
        fill_color, fill_opacity = _select_color(colors, "piece black")
        stroke_color, stroke_opacity = _select_color(colors, "piece black stroke")
        crown_color, crown_opacity = _select_color(colors, "crown black")

    # Draw the piece (circle)
    radius = SQUARE_SIZE * 0.4
    ET.SubElement(
        svg,
        "circle",
        _attrs(
            {
                "cx": x,
                "cy": y,
                "r": radius,
                "fill": fill_color,
                "stroke": stroke_color,
                "stroke-width": 2,
                "opacity": fill_opacity if fill_opacity < 1.0 else None,
            }
        ),
    )

    # Add crown for kings
    if is_king:
        # Scale and position the crown (crown path spans x=5 to x=23, y=2 to y=16)
        crown_width = 18  # 23 - 5
        crown_height = 14  # 16 - 2
        crown_scale = radius * 1.4 / crown_width
        crown_x = x - (crown_width / 2 + 5) * crown_scale  # Center horizontally
        crown_y = y - (crown_height / 2 + 2) * crown_scale  # Center vertically

        crown_g = ET.SubElement(
            svg,
            "g",
            _attrs(
                {
                    "transform": f"translate({crown_x}, {crown_y}) scale({crown_scale})",
                    "fill": crown_color,
                    "stroke": stroke_color,
                    "stroke-width": 1,
                    "opacity": crown_opacity if crown_opacity < 1.0 else None,
                }
            ),
        )
        ET.SubElement(crown_g, "path", {"d": CROWN_PATH})


def _render_coord(
    svg: ET.Element,
    text: str,
    x: float,
    y: float,
    colors: Dict[str, str],
) -> None:
    """Render a coordinate label."""
    coord_color, coord_opacity = _select_color(colors, "coord")

    ET.SubElement(
        svg,
        "text",
        _attrs(
            {
                "x": x,
                "y": y,
                "fill": coord_color,
                "font-size": 12,
                "font-family": "Arial, sans-serif",
                "text-anchor": "middle",
                "dominant-baseline": "central",
                "opacity": coord_opacity if coord_opacity < 1.0 else None,
            }
        ),
    ).text = text


def piece(
    piece_value: Union[int, Figure],
    *,
    size: Optional[int] = None,
    colors: Dict[str, str] = {},
) -> str:
    """
    Renders a single draughts piece as an SVG image.

    Args:
        piece_value: Piece value (-2=white king, -1=white man, 1=black man, 2=black king)
                    or a Figure enum value.
        size: Image size in pixels, or None for no size limit.
        colors: Dictionary to override default colors.

    Returns:
        SVG string wrapped in SvgWrapper for Jupyter integration.

    Example:
        >>> import draughts.svg
        >>> draughts.svg.piece(1)  # Black man
        >>> draughts.svg.piece(-2)  # White king
    """
    if isinstance(piece_value, Figure):
        piece_value = piece_value.value

    svg = _svg(SQUARE_SIZE, size)
    _render_piece(svg, piece_value, SQUARE_SIZE / 2, SQUARE_SIZE / 2, colors)

    return SvgWrapper(ET.tostring(svg, encoding="unicode"))


def board(
    board=None,
    *,
    size: Optional[int] = None,
    coordinates: bool = True,
    colors: Dict[str, str] = {},
    lastmove: Optional[Move] = None,
    arrows: Iterable[Union[Arrow, Tuple[int, int]]] = [],
    fill: Dict[int, str] = {},
    squares: Optional[Iterable[int]] = None,
    orientation: Color = Color.WHITE,
    legend: bool = True,
) -> str:
    """
    Renders a draughts board as an SVG image.

    Args:
        board: A BaseBoard instance, or None for an empty board.
        size: Image size in pixels, or None for no size limit.
        coordinates: Whether to show coordinate labels on the margin.
        colors: Dictionary to override default colors. Possible keys:
            - "square light", "square dark": Square colors
            - "square dark lastmove", "square light lastmove": Highlighted squares
            - "margin", "coord": Margin and coordinate colors
            - "piece white", "piece black": Piece fill colors
            - "piece white stroke", "piece black stroke": Piece outline colors
            - "crown white", "crown black": Crown colors for kings
            - "arrow green", "arrow red", "arrow yellow", "arrow blue": Arrow colors
        lastmove: A Move to highlight (shows start and end squares).
        arrows: List of Arrow objects or (tail, head) tuples to draw.
        fill: Dictionary mapping square indices to colors for highlighting.
        squares: Iterable of square indices to mark with an X.
        orientation: Viewing orientation (Color.WHITE = black at top).
        legend: Whether to show square numbers on the dark squares.

    Returns:
        SVG string wrapped in SvgWrapper for Jupyter integration.

    Example:
        >>> import draughts
        >>> import draughts.svg
        >>>
        >>> board = draughts.StandardBoard()
        >>> draughts.svg.board(board, size=400)
    """
    # Determine board dimensions
    if board is not None:
        board_size = board.shape[0]
        position = board.position
    else:
        board_size = 10  # Default to 10x10
        position = None

    num_playable_squares = (board_size * board_size) // 2

    # Calculate dimensions
    margin = MARGIN if coordinates else 0
    board_offset = margin
    full_size = 2 * margin + board_size * SQUARE_SIZE

    svg = _svg(full_size, size)

    # Add description if board provided
    if board is not None:
        desc = ET.SubElement(svg, "desc")
        pre = ET.SubElement(desc, "pre")
        pre.text = str(board)

    # Determine lastmove squares
    lastmove_squares = set()
    if lastmove is not None:
        if lastmove.square_list:
            lastmove_squares.add(lastmove.square_list[0])
            lastmove_squares.add(lastmove.square_list[-1])

    # Draw margin background
    if margin:
        margin_color, margin_opacity = _select_color(colors, "margin")
        ET.SubElement(
            svg,
            "rect",
            _attrs(
                {
                    "x": 0,
                    "y": 0,
                    "width": full_size,
                    "height": full_size,
                    "fill": margin_color,
                    "opacity": margin_opacity if margin_opacity < 1.0 else None,
                }
            ),
        )

    # Draw all squares (including light squares)
    for row in range(board_size):
        for col in range(board_size):
            # Apply orientation
            if orientation == Color.WHITE:
                x = col * SQUARE_SIZE + board_offset
                y = row * SQUARE_SIZE + board_offset
            else:
                x = (board_size - 1 - col) * SQUARE_SIZE + board_offset
                y = (board_size - 1 - row) * SQUARE_SIZE + board_offset

            # Determine if this is a dark (playable) square
            is_dark = (row + col) % 2 == 1

            # Calculate playable square index for dark squares
            square_idx = None
            if is_dark:
                squares_per_row = board_size // 2
                if row % 2 == 0:
                    square_idx = row * squares_per_row + (col - 1) // 2
                else:
                    square_idx = row * squares_per_row + col // 2

            # Determine square color
            if is_dark and square_idx in lastmove_squares:
                color_key = "square dark lastmove"
            elif not is_dark and square_idx in lastmove_squares:
                color_key = "square light lastmove"
            elif is_dark:
                color_key = "square dark"
            else:
                color_key = "square light"

            square_color, square_opacity = _select_color(colors, color_key)

            ET.SubElement(
                svg,
                "rect",
                _attrs(
                    {
                        "x": x,
                        "y": y,
                        "width": SQUARE_SIZE,
                        "height": SQUARE_SIZE,
                        "fill": square_color,
                        "stroke": "none",
                        "opacity": square_opacity if square_opacity < 1.0 else None,
                    }
                ),
            )

            # Apply custom fill color if specified
            if is_dark and square_idx is not None and square_idx in fill:
                fill_color, fill_opacity = _color(fill[square_idx])
                ET.SubElement(
                    svg,
                    "rect",
                    _attrs(
                        {
                            "x": x,
                            "y": y,
                            "width": SQUARE_SIZE,
                            "height": SQUARE_SIZE,
                            "fill": fill_color,
                            "stroke": "none",
                            "opacity": fill_opacity if fill_opacity < 1.0 else None,
                        }
                    ),
                )

    # Draw coordinate labels on margin (row numbers 1-N)
    if coordinates:
        for row in range(board_size):
            # Calculate Y position for this row
            coord_y: float
            if orientation == Color.WHITE:
                coord_y = row * SQUARE_SIZE + SQUARE_SIZE / 2 + board_offset
                row_label = str(board_size - row)  # Top row is highest number
            else:
                coord_y = row * SQUARE_SIZE + SQUARE_SIZE / 2 + board_offset
                row_label = str(row + 1)  # Bottom row is 1 when flipped

            # Left margin
            _render_coord(svg, row_label, margin / 2, coord_y, colors)

            # Right margin
            _render_coord(svg, row_label, full_size - margin / 2, coord_y, colors)

        # Draw column labels (a-j for 10x10, a-h for 8x8)
        col_labels = "abcdefghij"[:board_size]
        for col in range(board_size):
            coord_x: float
            if orientation == Color.WHITE:
                coord_x = col * SQUARE_SIZE + SQUARE_SIZE / 2 + board_offset
                col_label = col_labels[col]
            else:
                coord_x = col * SQUARE_SIZE + SQUARE_SIZE / 2 + board_offset
                col_label = col_labels[board_size - 1 - col]

            # Top margin
            _render_coord(svg, col_label, coord_x, margin / 2, colors)

            # Bottom margin
            _render_coord(svg, col_label, coord_x, full_size - margin / 2, colors)

    # Draw square numbers on dark squares (legend)
    if legend:
        for sq_idx in range(num_playable_squares):
            cx, cy = _get_square_center(sq_idx, board_size, orientation, board_offset)
            display_num = str(sq_idx + 1)

            # Draw small number in corner of square
            ET.SubElement(
                svg,
                "text",
                _attrs(
                    {
                        "x": cx - SQUARE_SIZE * 0.35,
                        "y": cy - SQUARE_SIZE * 0.3,
                        "fill": "#ffffff80",
                        "font-size": 9,
                        "font-family": "Arial, sans-serif",
                        "text-anchor": "start",
                        "dominant-baseline": "hanging",
                    }
                ),
            ).text = display_num

    # Draw pieces
    if position is not None:
        for sq_idx, piece_value in enumerate(position):
            if piece_value != 0:
                cx, cy = _get_square_center(
                    sq_idx, board_size, orientation, board_offset
                )
                _render_piece(svg, piece_value, cx, cy, colors)

    # Draw X markers on selected squares
    if squares:
        for sq_idx in squares:
            if 0 <= sq_idx < num_playable_squares:
                cx, cy = _get_square_center(
                    sq_idx, board_size, orientation, board_offset
                )
                # Draw an X
                size_half = SQUARE_SIZE * 0.3
                ET.SubElement(
                    svg,
                    "line",
                    _attrs(
                        {
                            "x1": cx - size_half,
                            "y1": cy - size_half,
                            "x2": cx + size_half,
                            "y2": cy + size_half,
                            "stroke": "#ff0000",
                            "stroke-width": 3,
                            "stroke-linecap": "round",
                        }
                    ),
                )
                ET.SubElement(
                    svg,
                    "line",
                    _attrs(
                        {
                            "x1": cx + size_half,
                            "y1": cy - size_half,
                            "x2": cx - size_half,
                            "y2": cy + size_half,
                            "stroke": "#ff0000",
                            "stroke-width": 3,
                            "stroke-linecap": "round",
                        }
                    ),
                )

    # Draw arrows
    for arrow in arrows:
        if isinstance(arrow, Arrow):
            tail, head, arrow_color = arrow.tail, arrow.head, arrow.color
        else:
            tail, head = arrow
            arrow_color = "green"

        color_key = f"arrow {arrow_color}"
        try:
            line_color, opacity = _select_color(colors, color_key)
        except KeyError:
            line_color, opacity = arrow_color, 1.0

        tail_x, tail_y = _get_square_center(tail, board_size, orientation, board_offset)
        head_x, head_y = _get_square_center(head, board_size, orientation, board_offset)

        if tail == head:
            # Circle for same square
            ET.SubElement(
                svg,
                "circle",
                _attrs(
                    {
                        "cx": head_x,
                        "cy": head_y,
                        "r": SQUARE_SIZE * 0.4,
                        "stroke-width": SQUARE_SIZE * 0.1,
                        "stroke": line_color,
                        "opacity": opacity if opacity < 1.0 else None,
                        "fill": "none",
                    }
                ),
            )
        else:
            # Arrow line with head
            marker_size = 0.75 * SQUARE_SIZE
            marker_margin = 0.1 * SQUARE_SIZE

            dx, dy = head_x - tail_x, head_y - tail_y
            hypot = math.hypot(dx, dy)

            shaft_x = head_x - dx * (marker_size + marker_margin) / hypot
            shaft_y = head_y - dy * (marker_size + marker_margin) / hypot

            xtip = head_x - dx * marker_margin / hypot
            ytip = head_y - dy * marker_margin / hypot

            ET.SubElement(
                svg,
                "line",
                _attrs(
                    {
                        "x1": tail_x,
                        "y1": tail_y,
                        "x2": shaft_x,
                        "y2": shaft_y,
                        "stroke": line_color,
                        "opacity": opacity if opacity < 1.0 else None,
                        "stroke-width": SQUARE_SIZE * 0.2,
                        "stroke-linecap": "butt",
                    }
                ),
            )

            # Arrow head
            marker = [
                (xtip, ytip),
                (
                    shaft_x + dy * 0.5 * marker_size / hypot,
                    shaft_y - dx * 0.5 * marker_size / hypot,
                ),
                (
                    shaft_x - dy * 0.5 * marker_size / hypot,
                    shaft_y + dx * 0.5 * marker_size / hypot,
                ),
            ]

            ET.SubElement(
                svg,
                "polygon",
                _attrs(
                    {
                        "points": " ".join(f"{x},{y}" for x, y in marker),
                        "fill": line_color,
                        "opacity": opacity if opacity < 1.0 else None,
                    }
                ),
            )

    return SvgWrapper(ET.tostring(svg, encoding="unicode"))
