"""Suggestions for worksheet names, dataset types and column types."""

import re

from auditor_support_tool.core.workbook_package import (
    DatasetType,
    MappingConfidence,
)
from auditor_support_tool.domains.financial_audit.general_ledger.data_profile_models import (
    ColumnProfile,
)


class WorkbookSuggestionService:
    """Generate editable preparation suggestions for workbook data."""

    _DATASET_KEYWORDS: tuple[
        tuple[DatasetType, tuple[str, ...]],
        ...,
    ] = (
        (
            DatasetType.GENERAL_LEDGER,
            (
                "general ledger",
                "general_ledger",
                "gl",
                "ledger",
            ),
        ),
        (
            DatasetType.CHART_OF_ACCOUNTS,
            (
                "chart of accounts",
                "chart_of_accounts",
                "coa",
                "accounts",
            ),
        ),
        (
            DatasetType.TRIAL_BALANCE,
            (
                "trial balance",
                "trial_balance",
                "tb",
            ),
        ),
        (
            DatasetType.VENDOR_MASTER,
            (
                "vendor master",
                "vendor_master",
                "vendors",
                "suppliers",
            ),
        ),
        (
            DatasetType.CUSTOMER_MASTER,
            (
                "customer master",
                "customer_master",
                "customers",
                "debtors",
            ),
        ),
        (
            DatasetType.BANK_TRANSACTIONS,
            (
                "bank transactions",
                "bank_transactions",
                "bank statement",
                "bank_statement",
            ),
        ),
        (
            DatasetType.PAYROLL_REGISTER,
            (
                "payroll register",
                "payroll_register",
                "payroll",
            ),
        ),
        (
            DatasetType.EMPLOYEE_MASTER,
            (
                "employee master",
                "employee_master",
                "employees",
                "staff",
            ),
        ),
        (
            DatasetType.FIXED_ASSET_REGISTER,
            (
                "fixed asset register",
                "fixed_asset_register",
                "assets",
                "far",
            ),
        ),
        (
            DatasetType.JOURNAL_LISTING,
            (
                "journal listing",
                "journal_listing",
                "journals",
            ),
        ),
        (
            DatasetType.USER_ACCESS_LISTING,
            (
                "user access",
                "user_access",
                "users",
                "access listing",
            ),
        ),
    )

    def suggest_dataset(
        self,
        worksheet_name: str,
        column_names: tuple[str, ...],
    ) -> tuple[str, DatasetType, MappingConfidence]:
        """Suggest a display name and dataset type."""

        normalised_sheet_name = self._normalise_text(worksheet_name)
        normalised_columns = {self._normalise_text(column_name) for column_name in column_names}

        best_type = DatasetType.UNCLASSIFIED
        best_score = 0

        for dataset_type, keywords in self._DATASET_KEYWORDS:
            score = 0

            for keyword in keywords:
                normalised_keyword = self._normalise_text(keyword)

                if normalised_keyword == normalised_sheet_name:
                    score += 5
                elif normalised_keyword in normalised_sheet_name:
                    score += 3

                if normalised_keyword in normalised_columns:
                    score += 2

            score += self._column_pattern_score(
                dataset_type,
                normalised_columns,
            )

            if score > best_score:
                best_score = score
                best_type = dataset_type

        confidence = self._confidence_from_score(best_score)

        suggested_name = (
            self.dataset_type_label(best_type)
            if best_type != DatasetType.UNCLASSIFIED
            else self._humanise_name(worksheet_name)
        )

        return (
            suggested_name,
            best_type,
            confidence,
        )

    def suggest_column_name(
        self,
        profile: ColumnProfile,
    ) -> tuple[str, MappingConfidence]:
        """Suggest a readable prepared name for a source column."""

        source_name = profile.column_name.strip()

        if not source_name:
            return (
                f"Column {profile.position}",
                MappingConfidence.LOW,
            )

        suggested_name = self._humanise_name(source_name)

        confidence = (
            MappingConfidence.HIGH if suggested_name != source_name else MappingConfidence.MEDIUM
        )

        return suggested_name, confidence

    @staticmethod
    def dataset_type_label(
        dataset_type: DatasetType,
    ) -> str:
        """Return a readable label for a dataset type."""

        labels = {
            DatasetType.GENERAL_LEDGER: "General Ledger",
            DatasetType.CHART_OF_ACCOUNTS: "Chart of Accounts",
            DatasetType.TRIAL_BALANCE: "Trial Balance",
            DatasetType.VENDOR_MASTER: "Vendor Master",
            DatasetType.CUSTOMER_MASTER: "Customer Master",
            DatasetType.BANK_TRANSACTIONS: "Bank Transactions",
            DatasetType.PAYROLL_REGISTER: "Payroll Register",
            DatasetType.EMPLOYEE_MASTER: "Employee Master",
            DatasetType.FIXED_ASSET_REGISTER: ("Fixed Asset Register"),
            DatasetType.JOURNAL_LISTING: "Journal Listing",
            DatasetType.USER_ACCESS_LISTING: ("User Access Listing"),
            DatasetType.OTHER: "Other",
            DatasetType.UNCLASSIFIED: "Unclassified",
        }

        return labels[dataset_type]

    @staticmethod
    def _column_pattern_score(
        dataset_type: DatasetType,
        columns: set[str],
    ) -> int:
        required_patterns: dict[
            DatasetType,
            tuple[tuple[str, ...], ...],
        ] = {
            DatasetType.GENERAL_LEDGER: (
                ("transaction date", "posting date"),
                ("account code", "account number"),
                ("debit", "credit", "amount"),
            ),
            DatasetType.CHART_OF_ACCOUNTS: (
                ("account code", "account number"),
                ("account name", "account description"),
                ("account type", "classification"),
            ),
            DatasetType.VENDOR_MASTER: (
                ("vendor number", "supplier number"),
                ("vendor name", "supplier name"),
            ),
            DatasetType.TRIAL_BALANCE: (
                ("account code", "account number"),
                ("debit balance", "debit"),
                ("credit balance", "credit"),
            ),
        }

        groups = required_patterns.get(dataset_type, ())
        score = 0

        for alternatives in groups:
            if any(alternative in columns for alternative in alternatives):
                score += 2

        return score

    @staticmethod
    def _confidence_from_score(
        score: int,
    ) -> MappingConfidence:
        if score >= 7:
            return MappingConfidence.HIGH

        if score >= 4:
            return MappingConfidence.MEDIUM

        if score >= 1:
            return MappingConfidence.LOW

        return MappingConfidence.NONE

    @staticmethod
    def _normalise_text(value: str) -> str:
        normalised = re.sub(
            r"[_\-]+",
            " ",
            value.strip().casefold(),
        )
        return re.sub(r"\s+", " ", normalised)

    @staticmethod
    def _humanise_name(value: str) -> str:
        normalised = re.sub(
            r"[_\-]+",
            " ",
            value.strip(),
        )
        normalised = re.sub(r"\s+", " ", normalised)

        return normalised.title()
