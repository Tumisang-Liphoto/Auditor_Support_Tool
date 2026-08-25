"""Generic dialog for configuring audit-procedure parameters."""

from __future__ import annotations

from copy import deepcopy
from typing import cast

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from auditor_support_tool.core.procedure_definition import ProcedureDefinition
from auditor_support_tool.core.procedure_parameter_models import (
    ProcedureParameterDefinition,
    ProcedureParameterType,
)
from auditor_support_tool.core.procedure_parameter_service import (
    ProcedureParameterValidationError,
    resolve_procedure_parameters,
)


class ProcedureParametersDialog(QDialog):
    """Render parameter inputs from a generic ProcedureDefinition."""

    def __init__(
        self,
        *,
        definition: ProcedureDefinition,
        initial_values: dict[str, object] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._definition = definition
        self._parameter_values: dict[str, object] = {}
        self._editors: dict[str, QWidget] = {}
        self._multi_choice_boxes: dict[str, tuple[QCheckBox, ...]] = {}

        self.setWindowTitle(f"Configure {definition.display_id} {definition.name}")
        self.setModal(True)
        self.setMinimumWidth(620)

        self._build_interface()
        self._apply_values(initial_values or {})

    @property
    def parameter_values(self) -> dict[str, object]:
        """Return validated values after the dialog has been accepted."""

        return deepcopy(self._parameter_values)

    def _build_interface(self) -> None:
        """Build parameter controls from the generic metadata contract."""

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 22, 24, 22)
        root_layout.setSpacing(16)

        title = QLabel(f"Configure {self._definition.display_id}  {self._definition.name}")
        title.setObjectName("dialogTitle")

        description = QLabel(
            "These settings are saved with the audit workspace and recorded "
            "with the procedure run. Optional settings may be left blank."
        )
        description.setObjectName("fieldHint")
        description.setWordWrap(True)

        root_layout.addWidget(title)
        root_layout.addWidget(description)

        for parameter in self._definition.parameter_definitions:
            root_layout.addWidget(self._build_parameter_section(parameter))

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)

        restore_button = QPushButton("Restore Defaults")
        restore_button.setObjectName("secondaryActionButton")
        restore_button.clicked.connect(self._restore_defaults)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )

        save_button = button_box.button(QDialogButtonBox.StandardButton.Save)

        if save_button is not None:
            save_button.setText("Save Settings")
            save_button.setDefault(True)

        button_box.accepted.connect(self._accept_values)
        button_box.rejected.connect(self.reject)

        buttons_layout.addWidget(restore_button)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(button_box)

        root_layout.addLayout(buttons_layout)

    def _build_parameter_section(
        self,
        parameter: ProcedureParameterDefinition,
    ) -> QFrame:
        """Create one labelled parameter input block."""

        section = QFrame()
        section.setObjectName("datasetMappingStatusRow")

        layout = QVBoxLayout(section)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        label_text = parameter.label

        if parameter.required:
            label_text += " *"

        label = QLabel(label_text)
        label.setObjectName("fieldLabel")

        layout.addWidget(label)

        if parameter.description:
            description = QLabel(parameter.description)
            description.setObjectName("fieldHint")
            description.setWordWrap(True)
            layout.addWidget(description)

        editor = self._create_editor(parameter)
        self._editors[parameter.key] = editor
        layout.addWidget(editor)

        return section

    def _create_editor(
        self,
        parameter: ProcedureParameterDefinition,
    ) -> QWidget:
        """Create the appropriate generic editor for one parameter type."""

        if parameter.value_type == ProcedureParameterType.BOOLEAN:
            editor = QCheckBox("Enabled")
            return editor

        if parameter.value_type == ProcedureParameterType.CHOICE:
            editor = QComboBox()

            if not parameter.required and parameter.default_value is None:
                editor.addItem("Not configured", None)

            for choice in parameter.choices:
                editor.addItem(choice, choice)

            return editor

        if parameter.value_type == ProcedureParameterType.MULTI_CHOICE:
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(18)

            boxes: list[QCheckBox] = []

            for choice in parameter.choices:
                checkbox = QCheckBox(choice)
                checkbox.setProperty("parameterChoice", choice)
                boxes.append(checkbox)
                layout.addWidget(checkbox)

            layout.addStretch(1)
            self._multi_choice_boxes[parameter.key] = tuple(boxes)
            return container

        editor = QLineEdit()
        editor.setClearButtonEnabled(True)

        if parameter.placeholder:
            editor.setPlaceholderText(parameter.placeholder)

        return editor

    def _apply_values(
        self,
        supplied_values: dict[str, object],
    ) -> None:
        """Populate editors from saved values, falling back to defaults."""

        for parameter in self._definition.parameter_definitions:
            if parameter.key in supplied_values:
                value = supplied_values[parameter.key]
            else:
                value = parameter.default_value

            self._set_editor_value(parameter, value)

    def _set_editor_value(
        self,
        parameter: ProcedureParameterDefinition,
        value: object | None,
    ) -> None:
        """Assign one value to its corresponding generic editor."""

        editor = self._editors[parameter.key]

        if parameter.value_type == ProcedureParameterType.BOOLEAN:
            cast(QCheckBox, editor).setChecked(bool(value))
            return

        if parameter.value_type == ProcedureParameterType.CHOICE:
            combo = cast(QComboBox, editor)

            if value is None:
                combo.setCurrentIndex(0 if combo.count() else -1)
                return

            target = str(value).casefold()

            for index in range(combo.count()):
                data = combo.itemData(index)

                if data is not None and str(data).casefold() == target:
                    combo.setCurrentIndex(index)
                    return

            combo.setCurrentIndex(0 if combo.count() else -1)
            return

        if parameter.value_type == ProcedureParameterType.MULTI_CHOICE:
            if isinstance(value, str):
                selected = {item.strip().casefold() for item in value.split(",") if item.strip()}
            elif isinstance(value, (list, tuple, set, frozenset)):
                selected = {str(item).strip().casefold() for item in value if str(item).strip()}
            else:
                selected = set()

            for checkbox in self._multi_choice_boxes.get(parameter.key, ()):
                choice = str(checkbox.property("parameterChoice") or "")
                checkbox.setChecked(choice.casefold() in selected)

            return

        line_edit = cast(QLineEdit, editor)

        if value is None:
            line_edit.clear()
        elif isinstance(value, (list, tuple)):
            line_edit.setText(", ".join(str(item) for item in value))
        else:
            line_edit.setText(str(value))

    def _collect_raw_values(self) -> dict[str, object]:
        """Collect unvalidated values from the generated editors."""

        values: dict[str, object] = {}

        for parameter in self._definition.parameter_definitions:
            editor = self._editors[parameter.key]

            if parameter.value_type == ProcedureParameterType.BOOLEAN:
                values[parameter.key] = cast(QCheckBox, editor).isChecked()
                continue

            if parameter.value_type == ProcedureParameterType.CHOICE:
                values[parameter.key] = cast(QComboBox, editor).currentData()
                continue

            if parameter.value_type == ProcedureParameterType.MULTI_CHOICE:
                values[parameter.key] = [
                    str(checkbox.property("parameterChoice") or "")
                    for checkbox in self._multi_choice_boxes.get(
                        parameter.key,
                        (),
                    )
                    if checkbox.isChecked()
                ]
                continue

            values[parameter.key] = cast(QLineEdit, editor).text()

        return values

    def _accept_values(self) -> None:
        """Validate the generated inputs before accepting the dialog."""

        try:
            self._parameter_values = resolve_procedure_parameters(
                self._definition,
                self._collect_raw_values(),
            )
        except ProcedureParameterValidationError as error:
            QMessageBox.warning(
                self,
                "Invalid Procedure Settings",
                str(error),
            )
            return

        self.accept()

    def _restore_defaults(self) -> None:
        """Restore defined defaults and clear optional custom settings."""

        self._apply_values({})
