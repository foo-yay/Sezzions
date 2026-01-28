"""Tests for Tools DTOs and schemas."""

import pytest
from sezzions.services.tools.dtos import (
    ValidationError,
    ValidationSeverity,
    ImportPreview,
    ImportResult,
    ValidationContext,
)
from sezzions.services.tools.schemas import (
    get_schema,
    get_all_schemas,
    get_exportable_schemas,
    PURCHASE_SCHEMA,
    USER_SCHEMA,
)
from sezzions.services.tools.enums import FieldType, PostImportHook


class TestValidationError:
    """Tests for ValidationError DTO."""
    
    def test_create_validation_error(self):
        """Test creating a validation error."""
        error = ValidationError(
            row_number=5,
            field='amount',
            value=-10,
            message='Amount must be positive',
            severity=ValidationSeverity.ERROR
        )
        
        assert error.row_number == 5
        assert error.field == 'amount'
        assert error.value == -10
        assert error.message == 'Amount must be positive'
        assert error.severity == ValidationSeverity.ERROR


class TestImportPreview:
    """Tests for ImportPreview DTO."""
    
    def test_has_errors_with_errors(self):
        """Test has_errors property when errors exist."""
        error = ValidationError(
            row_number=1,
            field='amount',
            value=None,
            message='Required',
            severity=ValidationSeverity.ERROR
        )
        
        preview = ImportPreview(
            to_add=[],
            to_update=[],
            exact_duplicates=[],
            conflicts=[],
            invalid_rows=[error],
            csv_duplicates=[]
        )
        
        assert preview.has_errors is True
        assert preview.has_warnings is False
    
    def test_has_warnings_with_warnings(self):
        """Test has_warnings property when warnings exist."""
        warning = ValidationError(
            row_number=2,
            field='notes',
            value='',
            message='Recommended field is empty',
            severity=ValidationSeverity.WARNING
        )
        
        preview = ImportPreview(
            to_add=[],
            to_update=[],
            exact_duplicates=[],
            conflicts=[],
            invalid_rows=[warning],
            csv_duplicates=[]
        )
        
        assert preview.has_errors is False
        assert preview.has_warnings is True
    
    def test_no_errors_or_warnings(self):
        """Test properties when no issues exist."""
        preview = ImportPreview(
            to_add=[{'id': 1}],
            to_update=[],
            exact_duplicates=[],
            conflicts=[],
            invalid_rows=[],
            csv_duplicates=[]
        )
        
        assert preview.has_errors is False
        assert preview.has_warnings is False


class TestImportResult:
    """Tests for ImportResult DTO."""
    
    def test_total_processed(self):
        """Test total_processed property."""
        result = ImportResult(
            success=True,
            records_added=10,
            records_updated=5,
            records_skipped=2
        )
        
        assert result.total_processed == 15
        assert result.success is True


class TestSchemas:
    """Tests for CSV schemas."""
    
    def test_get_schema_purchase(self):
        """Test retrieving purchase schema."""
        schema = get_schema('purchases')
        
        assert schema.table_name == 'purchases'
        assert schema.display_name == 'Purchases'
        assert schema.unique_columns == ('user_id', 'site_id', 'purchase_date', 'purchase_time')
        assert schema.post_import_hook == PostImportHook.PROMPT_RECALCULATE_EVERYTHING
    
    def test_get_schema_user(self):
        """Test retrieving user schema."""
        schema = get_schema('users')
        
        assert schema.table_name == 'users'
        assert schema.display_name == 'Users'
        assert schema.unique_columns == ('name',)
        assert schema.post_import_hook == PostImportHook.NONE
    
    def test_get_schema_invalid(self):
        """Test retrieving invalid schema raises KeyError."""
        with pytest.raises(KeyError, match="Unknown entity type"):
            get_schema('invalid_entity')
    
    def test_get_all_schemas(self):
        """Test retrieving all schemas."""
        schemas = get_all_schemas()
        
        assert len(schemas) == 9  # 9 entity types
        assert any(s.table_name == 'purchases' for s in schemas)
        assert any(s.table_name == 'users' for s in schemas)
    
    def test_get_exportable_schemas(self):
        """Test retrieving exportable schemas."""
        schemas = get_exportable_schemas()
        
        # All schemas should be exportable by default
        assert len(schemas) == 9
    
    def test_purchase_schema_fields(self):
        """Test purchase schema has required fields."""
        schema = PURCHASE_SCHEMA
        
        field_names = [f.db_column for f in schema.fields]
        
        assert 'user_id' in field_names
        assert 'site_id' in field_names
        assert 'purchase_date' in field_names
        assert 'amount' in field_names
        assert 'sc_received' in field_names
    
    def test_field_foreign_key_definition(self):
        """Test foreign key field definitions."""
        schema = PURCHASE_SCHEMA
        
        # Find user_id field
        user_field = next(f for f in schema.fields if f.db_column == 'user_id')
        
        assert user_field.field_type == FieldType.FOREIGN_KEY
        assert user_field.foreign_key is not None
        assert user_field.foreign_key.table == 'users'
        assert user_field.foreign_key.id_column == 'id'
        assert user_field.foreign_key.name_column == 'name'
    
    def test_field_required_flags(self):
        """Test required field flags."""
        schema = PURCHASE_SCHEMA
        
        # Required fields
        amount_field = next(f for f in schema.fields if f.db_column == 'amount')
        assert amount_field.required is True
        
        # Optional fields
        notes_field = next(f for f in schema.fields if f.db_column == 'notes')
        assert notes_field.required is False
    
    def test_field_default_values(self):
        """Test default values."""
        schema = PURCHASE_SCHEMA
        
        cashback_field = next(f for f in schema.fields if f.db_column == 'cashback_earned')
        assert cashback_field.default_value == '0.00'
        
        time_field = next(f for f in schema.fields if f.db_column == 'purchase_time')
        assert time_field.default_value == '00:00:00'
