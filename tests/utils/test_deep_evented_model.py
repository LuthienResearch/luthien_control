from unittest.mock import Mock

from luthien_control.utils.deep_evented_model import DeepEventedModel
from psygnal import EventedModel as PsygnalEventedModel
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

    def test_item_in_nested_list_of_models_emits_signal(self):
        """Test that changing an item in a list of models emits a signal."""

        class ItemModel(DeepEventedModel):
            value: int = 0

        class ParentModel(DeepEventedModel):
            items: EventedList[ItemModel] = Field(default_factory=lambda: EventedList[ItemModel]())

        # Initialize with a list containing a model
        parent = ParentModel(items=EventedList([ItemModel(value=1)]))
        mock_handler = Mock()
        parent.changed.connect(mock_handler)

        # Modify the model within the list
        parent.items[0].value = 2
        mock_handler.assert_called_once()
        mock_handler.reset_mock()

        # Add a new model and modify it
        new_item = ItemModel(value=10)
        parent.items.append(new_item)
        # two signals: inserting and inserted
        mock_handler.assert_called()
        mock_handler.reset_mock()

        # a change to the new item should also be detected
        new_item.value = 11
        mock_handler.assert_called_once()

    def test_deeply_nested_model_change_emits_signal(self):
        """Test a 3+ level deep change bubbles up."""

        class GrandChild(DeepEventedModel):
            name: str = "G"

        class Child(DeepEventedModel):
            grandchild: GrandChild = Field(default_factory=GrandChild)

        class Parent(DeepEventedModel):
            children: EventedList[Child] = Field(default_factory=lambda: EventedList[Child]())

        model = Parent(children=EventedList([Child()]))
        mock_handler = Mock()
        model.changed.connect(mock_handler)

        model.children[0].grandchild.name = "New Name"
        mock_handler.assert_called_once()

    def test_reassigning_nested_model_disconnects_old(self):
        """Test reassigning a nested model disconnects the old one."""

        class Child(DeepEventedModel):
            val: int = 0

        class Parent(DeepEventedModel):
            child: Child

        old_child = Child(val=1)
        model = Parent(child=old_child)
        mock_handler = Mock()
        model.changed.connect(mock_handler)

        # Reassign the child
        new_child = Child(val=2)
        model.child = new_child
        mock_handler.assert_called_once()
        mock_handler.reset_mock()

        # The new child should trigger events
        model.child.val = 3
        mock_handler.assert_called_once()
        mock_handler.reset_mock()

        # The old child should NOT trigger events
        old_child.val = 99
        mock_handler.assert_not_called()

    def test_item_in_nested_dict_of_models_emits_signal(self):
        """Test that changing an item in a dict of models emits a signal."""

        class ItemModel(DeepEventedModel):
            value: int = 0

        class ParentModel(DeepEventedModel):
            items: EventedDict[str, ItemModel] = Field(default_factory=lambda: EventedDict[str, ItemModel]())

        # Initialize with a dict containing a model
        parent = ParentModel(items=EventedDict({"first": ItemModel(value=1)}))
        mock_handler = Mock()
        parent.changed.connect(mock_handler)

        # Modify the model within the dict
        parent.items["first"].value = 2
        mock_handler.assert_called_once()
        mock_handler.reset_mock()

        # Add a new model and modify it
        new_item = ItemModel(value=10)
        parent.items["second"] = new_item
        mock_handler.assert_called()  # Fired for the dict `added` event
        mock_handler.reset_mock()

        # A change to the new item should also be detected
        new_item.value = 11
        mock_handler.assert_called_once()

    def test_generic_evented_object_emits_signal(self):
        """Test that a generic (non-Deep) evented object emits signals."""

        class GenericEvented(PsygnalEventedModel):
            value: int = 0

        class ParentModel(DeepEventedModel):
            generic: GenericEvented

        model = ParentModel(generic=GenericEvented(value=1))
        mock_handler = Mock()
        model.changed.connect(mock_handler)

        # Change on the generic model should be picked up
        model.generic.value = 2
        mock_handler.assert_called_once()
        mock_handler.reset_mock()

        # Test disconnection
        old_generic = model.generic
        model.generic = GenericEvented(value=10)
        mock_handler.assert_called_once()  # for the assignment
        mock_handler.reset_mock()

        # new one should emit
        model.generic.value = 11
        mock_handler.assert_called_once()
        mock_handler.reset_mock()

        # old one should not
        old_generic.value = 99
        mock_handler.assert_not_called()

    def test_generic_evented_item_in_list_emits_signal(self):
        """Test that a generic evented item in a list emits signals."""

        class GenericEventedItem(PsygnalEventedModel):
            value: int = 0

        class ParentModel(DeepEventedModel):
            items: EventedList[GenericEventedItem] = Field(default_factory=lambda: EventedList[GenericEventedItem]())

        model = ParentModel(items=EventedList([GenericEventedItem(value=1)]))
        mock_handler = Mock()
        model.changed.connect(mock_handler)

        # A change to the item in the list should be detected
        model.items[0].value = 2
        mock_handler.assert_called_once()
        mock_handler.reset_mock()

        # Adding a new item and changing it should also be detected
        new_item = GenericEventedItem(value=10)
        model.items.append(new_item)
        mock_handler.assert_called()
        mock_handler.reset_mock()

        new_item.value = 11
        mock_handler.assert_called_once()
        mock_handler.reset_mock()

        # Removing an item should disconnect it
        old_item = model.items[0]
        model.items.pop(0)
        mock_handler.assert_called()
        mock_handler.reset_mock()

        # The old, removed item should no longer emit signals
        old_item.value = 99
        mock_handler.assert_not_called()
