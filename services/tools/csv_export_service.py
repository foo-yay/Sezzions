"""
CSV Export Service

Exports database records to CSV files with proper formatting and FK resolution.
Supports template generation with example data.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from decimal import Decimal

from services.tools.dtos import ExportResult
from services.tools.schemas import get_schema
from services.tools.fk_resolver import ForeignKeyResolver
from services.tools.enums import FieldType
from services.tools.csv_utils import (
    format_date_for_export,
    format_time_for_export,
    format_decimal_for_export,
    format_boolean_for_export
)


class CSVExportService:
    """
    Service for exporting database records to CSV files.
    
    Handles:
    - Record export with proper formatting
    - Foreign key ID → name resolution
    - Template generation with example data
    - Type-safe value conversion
    """
    
    def __init__(self, db_connection):
        """
        Initialize the CSV export service.
        
        Args:
            db_connection: Database connection for querying records
        """
        self.db = db_connection
        self.fk_resolver = ForeignKeyResolver(db_connection)
    
    def export_to_csv(
        self,
        entity_type: str,
        output_path: str,
        filters: Optional[Dict[str, Any]] = None,
        include_inactive: bool = False
    ) -> ExportResult:
        """
        Export records to a CSV file.
        
        Args:
            entity_type: Type of entity to export (e.g., 'purchases', 'users')
            output_path: File path for output CSV
            filters: Optional filters to apply (e.g., {'site_id': 1, 'user_id': 2})
            include_inactive: Whether to include inactive records
            
        Returns:
            ExportResult with success status and record count
        """
        schema = get_schema(entity_type)
        
        # Load FK cache for this schema
        self.fk_resolver.load_cache_for_schema(schema)
        
        # Build query
        query, params = self._build_export_query(schema, filters, include_inactive)
        
        # Fetch records
        cursor = self.db.cursor()
        cursor.execute(query, params or [])
        records = cursor.fetchall()
        
        if not records:
            return ExportResult(
                success=True,
                records_exported=0,
                file_path=output_path,
                warnings=["No records found matching criteria"]
            )
        
        # Write CSV
        try:
            self._write_csv(schema, records, output_path)
            return ExportResult(
                success=True,
                records_exported=len(records),
                file_path=output_path
            )
        except Exception as e:
            return ExportResult(
                success=False,
                records_exported=0,
                file_path=output_path,
                errors=[f"Export failed: {str(e)}"]
            )
    
    def generate_template(
        self,
        entity_type: str,
        output_path: str,
        include_example_row: bool = True
    ) -> ExportResult:
        """
        Generate a CSV template with headers and optional example data.
        
        Args:
            entity_type: Type of entity template to generate (e.g., 'purchases')
            output_path: File path for output CSV
            include_example_row: Whether to include an example row
            
        Returns:
            ExportResult with success status
        """
        schema = get_schema(entity_type)
        
        try:
            # Write headers
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Header row
                headers = [field.csv_header for field in schema.fields]
                writer.writerow(headers)
                
                # Example row if requested
                if include_example_row:
                    example_row = self._generate_example_row(schema)
                    writer.writerow(example_row)
            
            return ExportResult(
                success=True,
                records_exported=1 if include_example_row else 0,
                file_path=output_path,
                warnings=["Template generated - edit example data before importing"]
            )
        except Exception as e:
            return ExportResult(
                success=False,
                records_exported=0,
                file_path=output_path,
                errors=[f"Template generation failed: {str(e)}"]
            )
    
    def _build_export_query(
        self,
        schema,
        filters: Optional[Dict[str, Any]],
        include_inactive: bool
    ) -> tuple[str, List[Any]]:
        """
        Build SQL query for exporting records.
        
        Args:
            schema: Entity schema
            filters: Optional filters
            include_inactive: Whether to include inactive records
            
        Returns:
            Tuple of (query_string, parameters)
        """
        # Select all columns
        query = f"SELECT * FROM {schema.table_name}"
        where_clauses = []
        params = []
        
        # Add is_active filter if applicable
        if not include_inactive and any(f.db_column == 'is_active' for f in schema.fields):
            where_clauses.append("is_active = 1")
        
        # Add custom filters
        if filters:
            for column, value in filters.items():
                where_clauses.append(f"{column} = ?")
                params.append(value)
        
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        # Order by chronologically for transaction tables
        # Use schema fields to find date/time column names
        date_col = next((f.db_column for f in schema.fields if f.field_type == FieldType.DATE), None)
        time_col = next((f.db_column for f in schema.fields if f.field_type == FieldType.TIME), None)
        
        if date_col and time_col:
            query += f" ORDER BY {date_col}, {time_col}"
        elif 'id' in [f.db_column for f in schema.fields]:
            query += " ORDER BY id"
        
        return query, params
    
    def _write_csv(self, schema, records: List, output_path: str):
        """
        Write records to CSV file with proper formatting.
        
        Args:
            schema: Entity schema
            records: Database records to export
            output_path: Output file path
        """
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            headers = [field.csv_header for field in schema.fields]
            writer.writerow(headers)
            
            # Write data rows
            for record in records:
                row = self._format_record_for_export(schema, record)
                writer.writerow(row)
    
    def _format_record_for_export(self, schema, record) -> List[str]:
        """
        Format a database record for CSV export.
        
        Args:
            schema: Entity schema
            record: Database record (sqlite3.Row or dict)
            
        Returns:
            List of formatted string values
        """
        formatted_row = []
        
        for field in schema.fields:
            # Get raw value from database
            raw_value = record[field.db_column] if field.db_column in record.keys() else None
            
            # Apply export formatting
            if raw_value is None:
                formatted_value = ""
            elif hasattr(field, 'export_formatter') and field.export_formatter:
                # Custom formatter
                formatted_value = field.export_formatter(raw_value)
            elif hasattr(field, 'foreign_key') and field.foreign_key:
                # FK: convert ID to name
                formatted_value = self._resolve_fk_for_export(
                    field.foreign_key.table,
                    raw_value
                )
            elif field.field_type == FieldType.DATE:
                formatted_value = format_date_for_export(raw_value)
            elif field.field_type == FieldType.TIME:
                formatted_value = format_time_for_export(raw_value)
            elif field.field_type == FieldType.DECIMAL:
                formatted_value = format_decimal_for_export(raw_value)
            elif field.field_type == FieldType.BOOLEAN:
                formatted_value = format_boolean_for_export(raw_value)
            else:
                formatted_value = str(raw_value)
            
            formatted_row.append(formatted_value)
        
        return formatted_row
    
    def _resolve_fk_for_export(self, fk_table: str, fk_id: Any) -> str:
        """
        Resolve foreign key ID to name for export.
        
        Args:
            fk_table: Foreign key table name
            fk_id: Foreign key ID value
            
        Returns:
            Resolved name or empty string if not found
        """
        if fk_id is None:
            return ""
        
        name = self.fk_resolver.get_name_for_id(fk_table, int(fk_id))
        return name if name else ""
    
    def _generate_example_row(self, schema) -> List[str]:
        """
        Generate an example row with sample data.
        
        Args:
            schema: Entity schema
            
        Returns:
            List of example values
        """
        example_row = []
        
        for field in schema.fields:
            if field.db_column == 'id':
                # Skip ID - will be auto-generated
                example_row.append("")
            elif hasattr(field, 'foreign_key') and field.foreign_key:
                # FK: use a generic name
                example_row.append(f"Example_{field.foreign_key.table.rstrip('s').title()}")
            elif field.field_type == FieldType.DATE:
                example_row.append("2026-01-27")
            elif field.field_type == FieldType.TIME:
                example_row.append("12:00:00")
            elif field.field_type == FieldType.DECIMAL:
                example_row.append("100.00")
            elif field.field_type == FieldType.BOOLEAN:
                example_row.append("1")
            elif field.field_type == FieldType.INTEGER:
                example_row.append("1")
            elif field.db_column in ('notes', 'comments'):
                example_row.append("Example note")
            elif 'name' in field.db_column.lower():
                example_row.append(f"Example {field.csv_header}")
            else:
                example_row.append("Example")
        
        return example_row


def export_with_timestamp(
    service: CSVExportService,
    entity_type: str,
    output_dir: str,
    filters: Optional[Dict[str, Any]] = None,
    include_inactive: bool = False
) -> ExportResult:
    """
    Export records with a timestamped filename.
    
    Args:
        service: CSV export service instance
        entity_type: Type of entity to export (e.g., 'purchases')
        output_dir: Directory for output file
        filters: Optional filters
        include_inactive: Whether to include inactive records
        
    Returns:
        ExportResult with success status and file path
    """
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{entity_type}_{timestamp}.csv"
    output_path = str(Path(output_dir) / filename)
    
    return service.export_to_csv(
        entity_type=entity_type,
        output_path=output_path,
        filters=filters,
        include_inactive=include_inactive
    )
