import numpy as np

from ...settings import get_settings
from ...utils.colormaps.standardize_color import transform_color
from ...utils.events import disconnect_events
from ..utils.gl import BLENDING_MODES
from ..utils.text import update_text
from ..visuals.points import PointsVisual
from .base import VispyBaseLayer


class VispyPointsLayer(VispyBaseLayer):
    _highlight_color = (0, 0.6, 1)
    _highlight_width = None

    def __init__(self, layer):
        self._highlight_width = get_settings().appearance.highlight_thickness

        node = PointsVisual()
        super().__init__(layer, node)

        self.layer.events.symbol.connect(self._on_data_change)
        self.layer.events.edge_width.connect(self._on_data_change)
        self.layer.events.edge_color.connect(self._on_data_change)
        self.layer._edge.events.colors.connect(self._on_data_change)
        self.layer._edge.events.color_properties.connect(self._on_data_change)
        self.layer.events.face_color.connect(self._on_data_change)
        self.layer._face.events.colors.connect(self._on_data_change)
        self.layer._face.events.color_properties.connect(self._on_data_change)
        self.layer.events.highlight.connect(self._on_highlight_change)
        self.layer.text.events.connect(self._on_text_change)

        self._on_data_change()

    def _on_data_change(self):
        if len(self.layer._indices_view) > 0:
            edge_color = self.layer._view_edge_color
            face_color = self.layer._view_face_color
        else:
            edge_color = np.array([[0.0, 0.0, 0.0, 1.0]], dtype=np.float32)
            face_color = np.array([[1.0, 1.0, 1.0, 1.0]], dtype=np.float32)

        # Set vispy data, noting that the order of the points needs to be
        # reversed to make the most recently added point appear on top
        # and the rows / columns need to be switched for vispy's x / y ordering
        if len(self.layer._indices_view) == 0:
            data = np.zeros((1, self.layer._ndisplay))
            size = [0]
        else:
            data = self.layer._view_data
            size = self.layer._view_size

        set_data = self.node._subvisuals[0].set_data

        set_data(
            data[:, ::-1],
            size=size,
            edge_width=self.layer.edge_width,
            symbol=self.layer.symbol,
            edge_color=edge_color,
            face_color=face_color,
            scaling=True,
        )

        self.reset()

    def _on_highlight_change(self):
        settings = get_settings()
        if len(self.layer._highlight_index) > 0:
            # Color the hovered or selected points
            data = self.layer._view_data[self.layer._highlight_index]
            if data.ndim == 1:
                data = np.expand_dims(data, axis=0)
            size = self.layer._view_size[self.layer._highlight_index]
        else:
            data = np.zeros((1, self.layer._ndisplay))
            size = 0

        self.node._subvisuals[1].set_data(
            data[:, ::-1],
            size=size,
            edge_width=settings.appearance.highlight_thickness,
            symbol=self.layer.symbol,
            edge_color=self._highlight_color,
            face_color=transform_color('transparent'),
            scaling=True,
        )

        # only draw a box in 2D
        if self.layer._ndisplay == 2:
            if (
                self.layer._highlight_box is None
                or 0 in self.layer._highlight_box.shape
            ):
                pos = np.zeros((1, self.layer._ndisplay))
                width = 0
            else:
                pos = self.layer._highlight_box
                width = settings.appearance.highlight_thickness

            self.node._subvisuals[2].set_data(
                pos=pos[:, ::-1],
                color=self._highlight_color,
                width=width,
            )
        else:
            self.node._subvisuals[2].set_data(
                pos=np.zeros((1, self.layer._ndisplay)),
                width=0,
            )

        self.node.update()

    def _update_text(self, *, update_node=True):
        """Function to update the text node properties

        Parameters
        ----------
        update_node : bool
            If true, update the node after setting the properties
        """
        ndisplay = self.layer._ndisplay
        if (len(self.layer._indices_view) == 0) or (
            self.layer.text.visible is False
        ):
            text_coords = np.zeros((1, ndisplay))
            text = []
            anchor_x = 'center'
            anchor_y = 'center'
        else:
            text_coords, anchor_x, anchor_y = self.layer._view_text_coords
            if len(text_coords) == 0:
                text_coords = np.zeros((1, ndisplay))
            text = self.layer._view_text
        text_node = self._get_text_node()
        update_text(
            text_values=text,
            coords=text_coords,
            anchor=(anchor_x, anchor_y),
            rotation=self.layer._text.rotation,
            color=self.layer._text.color,
            size=self.layer._text.size,
            ndisplay=ndisplay,
            text_node=text_node,
        )

        if update_node:
            self.node.update()

    def _get_text_node(self):
        """Function to get the text node from the Compound visual"""
        text_node = self.node._subvisuals[-1]
        return text_node

    def _on_text_change(self, event=None):
        if event is not None and event.type == 'blending':
            self._on_blending_change(event)
        else:
            self._update_text()

    def _on_blending_change(self):
        """Function to set the blending mode"""
        points_blending_kwargs = BLENDING_MODES[self.layer.blending]
        self.node.set_gl_state(**points_blending_kwargs)

        text_node = self._get_text_node()
        text_blending_kwargs = BLENDING_MODES[self.layer.text.blending]
        text_node.set_gl_state(**text_blending_kwargs)
        self.node.update()

    def reset(self, event=None):
        super().reset()
        self._update_text(update_node=False)
        self._on_blending_change()
        self._on_highlight_change()
        self._on_matrix_change()

    def close(self):
        """Vispy visual is closing."""
        disconnect_events(self.layer.text.events, self)
        super().close()
