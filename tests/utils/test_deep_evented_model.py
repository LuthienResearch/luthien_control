from unittest.mock import Mock

from luthien_control.utils.deep_evented_model import DeepEventedModel
from psygnal.containers import EventedDict, EventedList
from pydantic import Field


class TestDeepEventedModel:
    """Tests for the DeepEventedModel."""

    def test_top_level_field_change_emits_signal(self):
        """Test that changing a top-level field emits the `changed` signal."""

        class MyModel(DeepEventedModel):
            x: int = 0

        model = MyModel()
        mock_handler = Mock()
        model.changed.connect(mock_handler)

        model.x = 10
        mock_handler.assert_called_once()

    def test_evented_list_modification_emits_signal(self):
        """Test that modifying a nested EventedList emits the `changed` signal."""

        class MyModel(DeepEventedModel):
            items: EventedList[int] = Field(default_factory=lambda: EventedList[int]())

        model = MyModel(items=EventedList([1, 2]))
        mock_handler = Mock()
        model.changed.connect(mock_handler)

        model.items.append(3)
        mock_handler.assert_called()
        mock_handler.reset_mock()

        model.items[0] = 10
        mock_handler.assert_called()
        mock_handler.reset_mock()

        model.items.pop()
        mock_handler.assert_called()

    def test_evented_dict_modification_emits_signal(self):
        """Test that modifying a nested EventedDict emits the `changed` signal."""

        class MyModel(DeepEventedModel):
            data: EventedDict[str, int] = Field(default_factory=lambda: EventedDict[str, int]())

        model = MyModel(data=EventedDict({"a": 1}))
        mock_handler = Mock()
        model.changed.connect(mock_handler)

        model.data["b"] = 2
        mock_handler.assert_called()
        mock_handler.reset_mock()

        model.data["a"] = 10
        mock_handler.assert_called()
        mock_handler.reset_mock()

        del model.data["a"]
        mock_handler.assert_called()

    def test_nested_model_change_emits_signal(self):
        """Test that changing a field in a nested DeepEventedModel bubbles up."""

        class Nested(DeepEventedModel):
            y: int = 0

        class Parent(DeepEventedModel):
            nested: Nested

        model = Parent(nested=Nested(y=1))
        mock_handler = Mock()
        model.changed.connect(mock_handler)

        model.nested.y = 2
        mock_handler.assert_called_once()

    def test_reassigning_field_disconnects_old_child(self):
        """Test that reassigning a field disconnects the old evented object."""

        class MyModel(DeepEventedModel):
            items: EventedList[int]

        old_list = EventedList([1, 2])
        model = MyModel(items=old_list)
        mock_handler = Mock()
        model.changed.connect(mock_handler)

        new_list = EventedList([3, 4])
        model.items = new_list
        mock_handler.assert_called_once()  # Fired for the assignment
        mock_handler.reset_mock()

        # Changes to the new list should be detected
        new_list.append(5)
        mock_handler.assert_called()
        mock_handler.reset_mock()

        # Changes to the old list should NO LONGER be detected
        old_list.append(0)
        mock_handler.assert_not_called()

    def test_initialization_connects_children(self):
        """Test that children provided at initialization are connected."""

        class Nested(DeepEventedModel):
            y: int = 0

        class Parent(DeepEventedModel):
            nested: Nested
            items: EventedList[int]

        # Initialize with data
        model = Parent(nested=Nested(y=1), items=EventedList([10, 20]))
        mock_handler = Mock()
        model.changed.connect(mock_handler)

        # Verify connection to nested model
        model.nested.y = 2
        mock_handler.assert_called_once()
        mock_handler.reset_mock()

        # Verify connection to nested list
        model.items.append(30)
        mock_handler.assert_called()
