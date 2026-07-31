"""GitHub application-update configuration page."""

from datetime import datetime

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from auditor_support_tool.core.constants import APP_VERSION
from auditor_support_tool.gui.workers.update_check_worker import (
    UpdateCheckWorker,
)
from auditor_support_tool.services.settings_service import (
    SettingsService,
)
from auditor_support_tool.services.update_service import (
    UpdateCheckResult,
    UpdateService,
    UpdateStatus,
)


class UpdatesPage(QWidget):
    """Check GitHub Releases for application updates."""

    def __init__(
        self,
        settings_service: SettingsService,
        update_service: UpdateService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._settings_service = settings_service
        self._update_service = update_service

        self._worker: UpdateCheckWorker | None = None
        self._current_result: UpdateCheckResult | None = None

        self._channel_input = QComboBox()
        self._check_button = QPushButton()
        self._open_release_button = QPushButton()
        self._progress_bar = QProgressBar()

        self._status_badge = QLabel()
        self._status_message = QLabel()
        self._latest_version_value = QLabel()
        self._published_value = QLabel()
        self._package_value = QLabel()
        self._release_notes = QTextBrowser()

        self._build_interface()
        self._load_update_channel()

    def _build_interface(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("pageScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("pageContent")

        page_layout = QVBoxLayout(content)
        page_layout.setContentsMargins(40, 32, 40, 32)
        page_layout.setSpacing(22)
        page_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        page_title = QLabel("Updates")
        page_title.setObjectName("pageTitle")

        page_subtitle = QLabel(
            "Check GitHub Releases for improvements and corrections "
            "published for the Auditor Support Tool."
        )
        page_subtitle.setObjectName("pageSubtitle")
        page_subtitle.setWordWrap(True)

        page_layout.addWidget(page_title)
        page_layout.addWidget(page_subtitle)
        page_layout.addWidget(self._build_preferences_card())
        page_layout.addWidget(self._build_result_card())
        page_layout.addWidget(self._build_notes_card())

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area)

    def _build_preferences_card(self) -> QFrame:
        card = self._create_card()

        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(18)

        title = QLabel("Update preferences")
        title.setObjectName("profileSectionTitle")

        description = QLabel(
            "Stable includes production releases only. Testing may "
            "also include prerelease versions intended for evaluation."
        )
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        fields_layout = QGridLayout()
        fields_layout.setHorizontalSpacing(24)
        fields_layout.setVerticalSpacing(8)
        fields_layout.setColumnMinimumWidth(0, 300)
        fields_layout.setColumnStretch(0, 0)
        fields_layout.setColumnStretch(1, 1)

        channel_label = QLabel("Update channel")
        channel_label.setObjectName("fieldLabel")

        current_version_label = QLabel("Installed version")
        current_version_label.setObjectName("fieldLabel")

        self._channel_input.setObjectName("updateChannelInput")
        self._channel_input.setMinimumHeight(42)
        self._channel_input.setFixedWidth(280)
        self._channel_input.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._channel_input.setMinimumContentsLength(18)
        self._channel_input.addItem("Stable", "stable")
        self._channel_input.addItem("Testing", "testing")

        current_version_value = QLabel(APP_VERSION)
        current_version_value.setObjectName("updateValue")
        current_version_value.setMinimumHeight(42)

        channel_hint = QLabel("Choose which type of release the application should check.")
        channel_hint.setObjectName("fieldHint")
        channel_hint.setWordWrap(True)
        channel_hint.setMaximumWidth(300)

        version_hint = QLabel("The version currently running on this computer.")
        version_hint.setObjectName("fieldHint")
        version_hint.setWordWrap(True)

        fields_layout.addWidget(channel_label, 0, 0)
        fields_layout.addWidget(current_version_label, 0, 1)
        fields_layout.addWidget(
            self._channel_input,
            1,
            0,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )
        fields_layout.addWidget(current_version_value, 1, 1)
        fields_layout.addWidget(channel_hint, 2, 0)
        fields_layout.addWidget(version_hint, 2, 1)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)

        self._check_button.setText("Check for Updates")
        self._check_button.setObjectName("primaryActionButton")
        self._check_button.setFixedWidth(170)
        self._check_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._check_button.clicked.connect(self.check_for_updates)

        self._open_release_button.setText("Open Release Page")
        self._open_release_button.setObjectName("secondaryActionButton")
        self._open_release_button.setFixedWidth(165)
        self._open_release_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_release_button.setEnabled(False)
        self._open_release_button.clicked.connect(self.open_release_page)

        actions_layout.addWidget(self._check_button)
        actions_layout.addWidget(self._open_release_button)
        actions_layout.addStretch()

        self._progress_bar.setObjectName("updateProgress")
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setVisible(False)

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addLayout(fields_layout)
        layout.addLayout(actions_layout)
        layout.addWidget(self._progress_bar)

        return card

    def _build_result_card(self) -> QFrame:
        card = self._create_card()

        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(16)

        heading_layout = QHBoxLayout()
        heading_layout.setSpacing(12)

        heading_text_layout = QVBoxLayout()
        heading_text_layout.setSpacing(3)

        title = QLabel("Update status")
        title.setObjectName("profileSectionTitle")

        self._status_message.setText("No update check has been performed during this session.")
        self._status_message.setObjectName("profileSectionDescription")
        self._status_message.setWordWrap(True)

        self._status_badge.setText("NOT CHECKED")
        self._status_badge.setObjectName("updateStatusBadge")
        self._status_badge.setProperty("status", "neutral")
        self._status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        heading_text_layout.addWidget(title)
        heading_text_layout.addWidget(self._status_message)

        heading_layout.addLayout(heading_text_layout, 1)
        heading_layout.addWidget(
            self._status_badge,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        details_layout = QGridLayout()
        details_layout.setHorizontalSpacing(28)
        details_layout.setVerticalSpacing(10)
        details_layout.setColumnMinimumWidth(0, 170)
        details_layout.setColumnStretch(1, 1)

        self._latest_version_value.setText("Not checked")
        self._published_value.setText("Not available")
        self._package_value.setText("Not checked")

        for value_label in (
            self._latest_version_value,
            self._published_value,
            self._package_value,
        ):
            value_label.setObjectName("updateValue")
            value_label.setWordWrap(True)

        details_layout.addWidget(
            self._detail_label("Latest version"),
            0,
            0,
        )
        details_layout.addWidget(self._latest_version_value, 0, 1)
        details_layout.addWidget(
            self._detail_label("Published"),
            1,
            0,
        )
        details_layout.addWidget(self._published_value, 1, 1)
        details_layout.addWidget(
            self._detail_label("Windows package"),
            2,
            0,
        )
        details_layout.addWidget(self._package_value, 2, 1)

        layout.addLayout(heading_layout)
        layout.addLayout(details_layout)

        return card

    def _build_notes_card(self) -> QFrame:
        card = self._create_card()

        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(14)

        title = QLabel("Release notes")
        title.setObjectName("profileSectionTitle")

        description = QLabel(
            "Release notes for the latest applicable GitHub release will appear below."
        )
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        self._release_notes.setObjectName("releaseNotes")
        self._release_notes.setMinimumHeight(180)
        self._release_notes.setOpenExternalLinks(False)
        self._release_notes.setPlainText("No release information is available.")

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(self._release_notes)

        return card

    def _load_update_channel(self) -> None:
        channel = self._settings_service.get_update_channel()
        index = self._channel_input.findData(channel)

        if index < 0:
            index = self._channel_input.findData("stable")

        self._channel_input.setCurrentIndex(index)

    def check_for_updates(self) -> None:
        """Start a non-blocking GitHub update check."""

        if self._worker is not None and self._worker.isRunning():
            return

        channel = str(self._channel_input.currentData())
        self._settings_service.save_update_channel(channel)

        self._set_checking_state(True)
        self._current_result = None
        self._open_release_button.setEnabled(False)

        self._set_status(
            badge="CHECKING",
            message="Connecting to GitHub Releases…",
            status="checking",
        )

        self._latest_version_value.setText("Checking…")
        self._published_value.setText("Checking…")
        self._package_value.setText("Checking…")
        self._release_notes.setPlainText("Retrieving release information from GitHub.")

        self._worker = UpdateCheckWorker(
            update_service=self._update_service,
            channel=channel,
        )
        self._worker.completed.connect(self._handle_check_result)
        self._worker.failed.connect(self._handle_check_failure)
        self._worker.finished.connect(self._handle_worker_finished)
        self._worker.start()

    def _handle_check_result(
        self,
        result: UpdateCheckResult,
    ) -> None:
        self._current_result = result

        if result.status == UpdateStatus.AVAILABLE:
            badge = "UPDATE AVAILABLE"
            visual_status = "available"
        elif result.status == UpdateStatus.CURRENT:
            badge = "UP TO DATE"
            visual_status = "current"
        elif result.status == UpdateStatus.NO_RELEASES:
            badge = "NO RELEASES"
            visual_status = "warning"
        else:
            badge = "CHECK FAILED"
            visual_status = "error"

        self._set_status(
            badge=badge,
            message=result.message,
            status=visual_status,
        )

        release = result.release

        if release is None:
            self._latest_version_value.setText("Not available")
            self._published_value.setText("Not available")
            self._package_value.setText("Not available")
            self._release_notes.setPlainText(result.message)
            return

        self._latest_version_value.setText(str(release.version))
        self._published_value.setText(self._format_published_at(release.published_at))

        if result.package_asset is None:
            package_text = "Release found, but the Windows package has not been attached."
        elif result.checksum_asset is None:
            package_text = "Package found, but the SHA-256 checksum file is missing."
        else:
            package_text = "Package and SHA-256 checksum are available."

        self._package_value.setText(package_text)

        notes = release.release_notes.strip()
        self._release_notes.setPlainText(notes or "No release notes were provided.")

        self._open_release_button.setEnabled(bool(release.release_url))

    def _handle_check_failure(self, message: str) -> None:
        self._set_status(
            badge="CHECK FAILED",
            message=message,
            status="error",
        )

        self._latest_version_value.setText("Not available")
        self._published_value.setText("Not available")
        self._package_value.setText("Not available")
        self._release_notes.setPlainText(message)

    def _handle_worker_finished(self) -> None:
        self._set_checking_state(False)

        worker = self._worker
        self._worker = None

        if worker is not None:
            worker.deleteLater()

    def open_release_page(self) -> None:
        """Open the selected GitHub release in the default browser."""

        if self._current_result is None or self._current_result.release is None:
            return

        release_url = self._current_result.release.release_url

        if release_url:
            QDesktopServices.openUrl(QUrl(release_url))

    def _set_checking_state(self, checking: bool) -> None:
        self._channel_input.setEnabled(not checking)
        self._check_button.setEnabled(not checking)
        self._progress_bar.setVisible(checking)

    def _set_status(
        self,
        badge: str,
        message: str,
        status: str,
    ) -> None:
        self._status_badge.setText(badge)
        self._status_badge.setProperty("status", status)
        self._status_message.setText(message)

        style = self._status_badge.style()
        style.unpolish(self._status_badge)
        style.polish(self._status_badge)

    @staticmethod
    def _format_published_at(published_at: str) -> str:
        if not published_at:
            return "Not specified"

        try:
            parsed = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except ValueError:
            return published_at

        return parsed.strftime("%d %B %Y, %H:%M UTC")

    @staticmethod
    def _detail_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    @staticmethod
    def _create_card() -> QFrame:
        card = QFrame()
        card.setObjectName("profileSectionCard")
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        return card
