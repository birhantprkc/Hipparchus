"""How big the exported sheet actually is, in inches on paper.

Paper used to be a table of *pixel* sizes in `ui/main_window.py`: `A4` meant
2480 x 3508, because that is A4 at 300 dpi, and the number 300 appeared nowhere.
That works exactly as long as every exporter wants pixels, and one of them does
not. Skia takes a PDF page in **points**, 72 to the inch, so those same numbers
were handed to `beginPage` and wrote a page 34.4 x 48.7 inches — every PDF this
application has exported is 4.167x too large in each dimension, 17.4x in area.

Saying it in inches instead makes one description serve all three. Pixels are
inches x dpi for the bitmap, points are inches x 72 for the PDF, and SVG keeps
taking pixels because that is what an SVG viewport is. A sheet asked for at
24 x 36 is the same sheet in every format, which is the whole point of having a
page size rather than a canvas size.

Ported from `PageSize.swift` in the macOS application, which solved this first.
The two are kept deliberately close: same sheets, same resolutions, same
fallbacks, so a sheet named in one is the same sheet in the other.

This lives in `application/` rather than in the window because all of it can be
decided without a widget, and none of it could be checked while it lived in one.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class PaperSize:
    """A sheet, in inches, stated portrait — the long edge is the height.

    `PageSpec.orientation` turns it. The table states one of the two so that
    turning a sheet is a single rule rather than twenty entries.
    """

    name: str
    width_inches: float
    height_inches: float

    @property
    def is_canvas(self) -> bool:
        """The sheet that means "keep whatever size the canvas already was"."""
        return self.width_inches <= 0 or self.height_inches <= 0

    @staticmethod
    def canvas() -> PaperSize:
        return PaperSize("Canvas", 0.0, 0.0)

    CUSTOM_NAME = "Custom"

    @property
    def is_custom(self) -> bool:
        """A sheet whose two numbers come from `PageSpec`, not from this table."""
        return self.name == PaperSize.CUSTOM_NAME

    @staticmethod
    def custom_placeholder() -> PaperSize:
        """Stands in the menu; the real dimensions live on the `PageSpec`.

        20 x 12 so the default custom sheet is 5:3 — at 150 dpi that is
        3000 x 1800, the aspect a whole-earth sheet is most often asked for.
        """
        return PaperSize(PaperSize.CUSTOM_NAME, 20.0, 12.0)

    @staticmethod
    def all() -> tuple[PaperSize, ...]:
        """The offered sheets: ISO and US paper for documents, then the three
        sizes people actually frame — the last is the 24 x 36 a print shop
        treats as a standard poster."""
        return (
            PaperSize.canvas(),
            PaperSize.custom_placeholder(),
            PaperSize("Square", 20.0, 20.0),
            PaperSize("A4", 8.268, 11.693),
            PaperSize("A3", 11.693, 16.535),
            PaperSize("A2", 16.535, 23.386),
            PaperSize("Letter", 8.5, 11.0),
            PaperSize("Tabloid", 11.0, 17.0),
            PaperSize("12 x 18 in", 12.0, 18.0),
            PaperSize("18 x 24 in", 18.0, 24.0),
            PaperSize("24 x 36 in", 24.0, 36.0),
        )

    @staticmethod
    def names() -> tuple[str, ...]:
        return tuple(paper.name for paper in PaperSize.all())

    @staticmethod
    def named(name: str) -> PaperSize:
        """An unknown name behaves as Canvas rather than as a zero-size page.

        A restored session or a saved preset can name a sheet a later build has
        renamed — `Square 2048` was one of these — and an export that quietly
        becomes canvas-sized is a smaller surprise than one that fails.
        """
        for paper in PaperSize.all():
            if paper.name == name:
                return paper
        return PaperSize.canvas()


class Resolution:
    """The resolutions offered, and what each is for.

    Not a free number: a text field invites 1200 dpi on a 24 x 36 sheet, which
    is 1.2 gigapixels and several minutes of drawing before it fails.
    """

    DEFAULT = 300

    @staticmethod
    def all() -> tuple[int, ...]:
        return (72, 150, 300, 600)

    @staticmethod
    def label(dpi: int | float) -> str:
        return {
            72: "72 dpi · screen",
            150: "150 dpi · proof",
            300: "300 dpi · print",
            600: "600 dpi · fine",
        }.get(int(dpi), f"{int(dpi)} dpi")


#: What a bitmap export refuses past. Chosen so 24 x 36 at 300 dpi — the sheet
#: this feature exists for, at 78 megapixels — is comfortably inside it, and the
#: same sheet at 600 dpi is not.
MAXIMUM_MEGAPIXELS = 120.0

#: A canvas-sized PDF reads the canvas as CSS pixels, 96 to the inch, which
#: turns a 2400-pixel canvas into a sensible 25-inch sheet instead of a 33-foot
#: one. Only reached when no paper has been chosen.
CSS_PIXELS_PER_INCH = 96.0

POINTS_PER_INCH = 72.0


@dataclass(frozen=True, slots=True)
class PageSpec:
    """A page: a sheet, which way up, and how finely to draw it."""

    paper_name: str = "Canvas"
    orientation: str = "Landscape"
    dpi: int = Resolution.DEFAULT
    #: The Custom sheet's two numbers, in inches. Read only when `paper_name`
    #: is "Custom", and kept while another sheet is selected so coming back to
    #: Custom finds what was last typed.
    custom_width_inches: float = 20.0
    custom_height_inches: float = 12.0

    ORIENTATIONS = ("Landscape", "Portrait")
    #: The smallest and largest a custom edge may be. A sheet of zero is not a
    #: sheet, and one of a thousand inches is a bitmap nothing can allocate.
    CUSTOM_INCH_RANGE = (1.0, 200.0)

    @property
    def paper(self) -> PaperSize:
        named = PaperSize.named(self.paper_name)
        if not named.is_custom:
            return named
        low, high = PageSpec.CUSTOM_INCH_RANGE
        return PaperSize(
            PaperSize.CUSTOM_NAME,
            min(max(self.custom_width_inches, low), high),
            min(max(self.custom_height_inches, low), high),
        )

    @property
    def custom_aspect_description(self) -> str:
        """The custom sheet's proportions, said as a ratio a reader can check."""
        paper = self.paper
        if not paper.is_custom or paper.height_inches <= 0:
            return ""
        return f"{paper.width_inches / paper.height_inches:.3f} : 1"

    def inches(self) -> tuple[float, float] | None:
        """The sheet in inches, turned to the chosen orientation.

        The orientation turns the *sheet*, not the map — the rule the SVG
        composition has always used — so a landscape A4 is 11.7 x 8.3 rather
        than a rotated drawing. `None` for Canvas, which has no stated size.
        """
        paper = self.paper
        if paper.is_canvas:
            return None
        width, height = paper.width_inches, paper.height_inches
        if paper.is_custom:
            # Orientation turns a *named* sheet, because "A4" says nothing
            # about which way up. A custom sheet is two numbers the reader
            # typed: 20 x 12 means 20 wide, and silently turning it to 12 x 20
            # would be overruling the only statement they made.
            return (width, height)
        if self.orientation == "Landscape" and height > width:
            width, height = height, width
        elif self.orientation == "Portrait" and width > height:
            width, height = height, width
        return (width, height)

    def pixel_size(self, canvas_width: int, canvas_height: int) -> tuple[int, int]:
        """Pixels, for a bitmap and for the SVG viewport.

        Canvas falls back to the size the caller already had.
        """
        inches = self.inches()
        if inches is None:
            return (max(1, int(canvas_width)), max(1, int(canvas_height)))
        resolution = max(1, int(self.dpi))
        return (
            max(1, round(inches[0] * resolution)),
            max(1, round(inches[1] * resolution)),
        )

    def point_size(self, canvas_width: int, canvas_height: int) -> tuple[float, float]:
        """PostScript points, for a PDF. 72 to the inch, by definition.

        So a PDF carries the physical size rather than a resolution, and prints
        at the requested dimensions on any device. The resolution is not part of
        this, and that is the whole correction: `dpi` decides how finely the
        bitmap is drawn and has nothing to say about how big the paper is.
        """
        inches = self.inches()
        if inches is None:
            return (
                max(1, int(canvas_width)) * POINTS_PER_INCH / CSS_PIXELS_PER_INCH,
                max(1, int(canvas_height)) * POINTS_PER_INCH / CSS_PIXELS_PER_INCH,
            )
        return (inches[0] * POINTS_PER_INCH, inches[1] * POINTS_PER_INCH)

    def bitmap_cost(self, canvas_width: int, canvas_height: int) -> tuple[float, float]:
        """What a bitmap of this page would cost, before drawing it.

        Megapixels and megabytes of premultiplied RGBA. Measuring first means a
        refusal can say what was actually asked for.
        """
        width, height = self.pixel_size(canvas_width, canvas_height)
        pixels = float(width) * float(height)
        return (pixels / 1_000_000.0, pixels * 4.0 / 1_000_000.0)

    def exceeds_bitmap_limit(self, canvas_width: int, canvas_height: int) -> bool:
        return self.bitmap_cost(canvas_width, canvas_height)[0] > MAXIMUM_MEGAPIXELS

    @staticmethod
    def custom_inches(text: str) -> tuple[float, float] | None:
        """Two inch numbers, said the way someone types them.

        ``20x12``, ``5:3``, ``20,12``. `None` if that is not what the text is,
        so the caller can say what it wanted rather than guessing at a sheet.

        Ported from `PageSpec.customInches(parsing:)` on the Mac, where it
        exists because the command line tool cannot be imported by a test. Here
        it could have lived in the script, but the two are kept together so a
        sheet asked for in one application is the same sheet in the other.
        """
        # Lowercased first: the separator is `x`, and somebody typing 20X12
        # means the same sheet as somebody typing 20x12.
        lowered = text.lower()
        for separator in ("x", ":", ","):
            lowered = lowered.replace(separator, " ")
        parts = lowered.split()
        if len(parts) != 2:
            return None
        try:
            width, height = float(parts[0]), float(parts[1])
        except ValueError:
            return None
        if width <= 0 or height <= 0:
            return None
        return (width, height)

    def with_custom_size(self, width_inches: float, height_inches: float) -> PageSpec:
        """The same page, on a sheet of exactly these inches.

        A copy, this being a frozen dataclass — and the resolution comes along
        untouched, since inches only become pixels once a dpi is applied.
        """
        return replace(
            self,
            paper_name=PaperSize.CUSTOM_NAME,
            custom_width_inches=width_inches,
            custom_height_inches=height_inches,
        )

    def describe(self, canvas_width: int, canvas_height: int) -> str:
        """One line under the controls: the sheet, its pixels and what it costs.

        A person asking for 600 dpi on a poster should see the number before
        they wait for it, not after the export fails.
        """
        width, height = self.pixel_size(canvas_width, canvas_height)
        megapixels, _ = self.bitmap_cost(canvas_width, canvas_height)
        inches = self.inches()
        if inches is None:
            return f"Canvas · {width} × {height} px · {megapixels:.1f} MP"
        return (
            f"{inches[0]:.2f} × {inches[1]:.2f} in · "
            f"{width} × {height} px · {megapixels:.1f} MP"
        )
