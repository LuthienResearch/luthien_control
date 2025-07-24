from typing import Optional
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

    def test_evented_containers_serialization_base_class(self):
        """Test that EventedList and EventedDict are automatically serialized by the base class."""

        class ModelWithEventedContainers(DeepEventedModel):
            items: EventedList[str] = Field(default_factory=lambda: EventedList[str]())
            metadata: EventedDict[str, int] = Field(default_factory=lambda: EventedDict[str, int]())
            # No field serializers - relying on base class model_serializer

        # Create model with evented containers
        model = ModelWithEventedContainers(
            items=EventedList(["a", "b", "c"]), metadata=EventedDict({"count": 3, "version": 1})
        )

        # Serialize the model
        serialized = model.model_dump()

        # Check that EventedList became a regular list
        assert isinstance(serialized["items"], list)
        assert serialized["items"] == ["a", "b", "c"]

        # Check that EventedDict became a regular dict
        assert isinstance(serialized["metadata"], dict)
        assert serialized["metadata"] == {"count": 3, "version": 1}

        # Verify the original model still has evented containers
        assert isinstance(model.items, EventedList)
        assert isinstance(model.metadata, EventedDict)

    def test_nested_evented_containers_serialization(self):
        """Test that nested models with EventedList and EventedDict serialize correctly using base class."""

        class InnerModel(DeepEventedModel):
            tags: EventedList[str] = Field(default_factory=lambda: EventedList[str]())
            # No field serializers - relying on base class model_serializer

        class OuterModel(DeepEventedModel):
            inner: InnerModel
            settings: EventedDict[str, str] = Field(default_factory=lambda: EventedDict[str, str]())
            # No field serializers - relying on base class model_serializer

        # Create nested model
        model = OuterModel(
            inner=InnerModel(tags=EventedList(["python", "pydantic"])),
            settings=EventedDict({"theme": "dark", "lang": "en"}),
        )

        # Serialize the model
        serialized = model.model_dump()

        # Check that nested EventedList became a regular list
        assert isinstance(serialized["inner"]["tags"], list)
        assert serialized["inner"]["tags"] == ["python", "pydantic"]

        # Check that EventedDict became a regular dict
        assert isinstance(serialized["settings"], dict)
        assert serialized["settings"] == {"theme": "dark", "lang": "en"}

    def test_serialization_preserves_functionality(self):
        """Test that base class serialization doesn't break the evented functionality."""

        class TestModel(DeepEventedModel):
            items: EventedList[int] = Field(default_factory=lambda: EventedList[int]())
            # No field serializers - relying on base class model_serializer

        model = TestModel(items=EventedList([1, 2, 3]))
        mock_handler = Mock()
        model.changed.connect(mock_handler)

        # Serialize the model
        serialized = model.model_dump()
        assert isinstance(serialized["items"], list)
        assert serialized["items"] == [1, 2, 3]

        # Verify that evented functionality still works after serialization
        model.items.append(4)
        mock_handler.assert_called()

        # Verify the original container is still evented
        assert isinstance(model.items, EventedList)
        assert list(model.items) == [1, 2, 3, 4]

    def test_mixed_field_types_serialization(self):
        """Test that models with mixed field types serialize correctly."""

        class MixedModel(DeepEventedModel):
            evented_list: EventedList[str] = Field(default_factory=lambda: EventedList[str]())
            evented_dict: EventedDict[str, int] = Field(default_factory=lambda: EventedDict[str, int]())
            regular_list: list[str] = Field(default_factory=list)
            regular_dict: dict[str, int] = Field(default_factory=dict)
            simple_field: str = "test"
            optional_field: Optional[str] = None

        model = MixedModel(
            evented_list=EventedList(["a", "b"]),
            evented_dict=EventedDict({"x": 1, "y": 2}),
            regular_list=["c", "d"],
            regular_dict={"z": 3},
            simple_field="hello",
        )

        serialized = model.model_dump()

        # EventedList should become regular list
        assert isinstance(serialized["evented_list"], list)
        assert serialized["evented_list"] == ["a", "b"]

        # EventedDict should become regular dict
        assert isinstance(serialized["evented_dict"], dict)
        assert serialized["evented_dict"] == {"x": 1, "y": 2}

        # Regular fields should be unchanged
        assert isinstance(serialized["regular_list"], list)
        assert serialized["regular_list"] == ["c", "d"]
        assert isinstance(serialized["regular_dict"], dict)
        assert serialized["regular_dict"] == {"z": 3}
        assert serialized["simple_field"] == "hello"
        assert serialized["optional_field"] is None

    def test_empty_evented_containers_serialization(self):
        """Test that empty EventedList and EventedDict serialize correctly."""

        class EmptyModel(DeepEventedModel):
            empty_list: EventedList[str] = Field(default_factory=lambda: EventedList[str]())
            empty_dict: EventedDict[str, int] = Field(default_factory=lambda: EventedDict[str, int]())

        model = EmptyModel()
        serialized = model.model_dump()

        # Empty containers should serialize to empty regular containers
        assert isinstance(serialized["empty_list"], list)
        assert serialized["empty_list"] == []
        assert isinstance(serialized["empty_dict"], dict)
        assert serialized["empty_dict"] == {}

    def test_deeply_nested_evented_models_serialization(self):
        """Test serialization of deeply nested models with evented containers."""

        class Level3Model(DeepEventedModel):
            data: EventedList[str] = Field(default_factory=lambda: EventedList[str]())

        class Level2Model(DeepEventedModel):
            level3: Level3Model
            metadata: EventedDict[str, str] = Field(default_factory=lambda: EventedDict[str, str]())

        class Level1Model(DeepEventedModel):
            level2: Level2Model
            tags: EventedList[str] = Field(default_factory=lambda: EventedList[str]())

        model = Level1Model(
            level2=Level2Model(
                level3=Level3Model(data=EventedList(["deep", "data"])), metadata=EventedDict({"level": "2"})
            ),
            tags=EventedList(["top", "level"]),
        )

        serialized = model.model_dump()

        # Check all levels serialize correctly
        assert isinstance(serialized["tags"], list)
        assert serialized["tags"] == ["top", "level"]

        assert isinstance(serialized["level2"], dict)
        assert isinstance(serialized["level2"]["metadata"], dict)
        assert serialized["level2"]["metadata"] == {"level": "2"}

        assert isinstance(serialized["level2"]["level3"], dict)
        assert isinstance(serialized["level2"]["level3"]["data"], list)
        assert serialized["level2"]["level3"]["data"] == ["deep", "data"]

    def test_serialization_with_complex_nested_objects(self):
        """Test serialization of EventedList containing complex objects."""

        class Item(DeepEventedModel):
            name: str
            tags: EventedList[str] = Field(default_factory=lambda: EventedList[str]())

        class Container(DeepEventedModel):
            items: EventedList[Item] = Field(default_factory=lambda: EventedList[Item]())
            item_map: EventedDict[str, Item] = Field(default_factory=lambda: EventedDict[str, Item]())

        item1 = Item(name="item1", tags=EventedList(["tag1", "tag2"]))
        item2 = Item(name="item2", tags=EventedList(["tag3"]))

        model = Container(items=EventedList([item1, item2]), item_map=EventedDict({"first": item1, "second": item2}))

        serialized = model.model_dump()

        # Check that EventedList of models serializes correctly
        assert isinstance(serialized["items"], list)
        assert len(serialized["items"]) == 2
        assert isinstance(serialized["items"][0], dict)
        assert serialized["items"][0]["name"] == "item1"
        assert isinstance(serialized["items"][0]["tags"], list)
        assert serialized["items"][0]["tags"] == ["tag1", "tag2"]

        # Check that EventedDict of models serializes correctly
        assert isinstance(serialized["item_map"], dict)
        assert isinstance(serialized["item_map"]["first"], dict)
        assert serialized["item_map"]["first"]["name"] == "item1"
        assert isinstance(serialized["item_map"]["first"]["tags"], list)
        assert serialized["item_map"]["first"]["tags"] == ["tag1", "tag2"]

    def test_no_pydantic_warnings_during_serialization(self):
        """Test that serializing EventedList/EventedDict produces no Pydantic warnings."""
        import warnings

        class TestModel(DeepEventedModel):
            messages: EventedList[str] = Field(default_factory=lambda: EventedList[str]())
            metadata: EventedDict[str, str] = Field(default_factory=lambda: EventedDict[str, str]())

        model = TestModel(messages=EventedList(["hello", "world"]), metadata=EventedDict({"key": "value"}))

        # Capture warnings during serialization
        with warnings.catch_warnings(record=True) as warning_list:
            warnings.simplefilter("always")  # Capture all warnings
            serialized = model.model_dump()

        # Filter for Pydantic serialization warnings
        pydantic_warnings = [w for w in warning_list if "PydanticSerializationUnexpectedValue" in str(w.message)]

        # Should be no Pydantic serialization warnings
        assert len(pydantic_warnings) == 0, f"Found Pydantic warnings: {[str(w.message) for w in pydantic_warnings]}"

        # Verify serialization worked correctly
        assert isinstance(serialized["messages"], list)
        assert serialized["messages"] == ["hello", "world"]
        assert isinstance(serialized["metadata"], dict)
        assert serialized["metadata"] == {"key": "value"}
