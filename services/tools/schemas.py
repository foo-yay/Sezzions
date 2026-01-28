"""CSV schema definitions for all entity types.

Defines the structure of CSV files for import/export, including:
- Column mappings (CSV header <-> DB column)
- Data types and validation rules
- Foreign key relationships
- Unique constraints for duplicate detection
"""

from dataclasses import dataclass
from typing import Optional, Callable, Any, Tuple, List
from .enums import FieldType, PostImportHook


@dataclass
class ForeignKeyDef:
    """Definition of a foreign key relationship."""
    table: str          # Target table name
    id_column: str      # Target ID column (usually 'id')
    name_column: str    # Target name column for CSV resolution


@dataclass
class CSVFieldDef:
    """Definition of a single CSV column."""
    db_column: str          # Database column name
    csv_header: str         # Human-readable CSV header
    field_type: FieldType   # Data type
    required: bool          # Whether field is required
    foreign_key: Optional[ForeignKeyDef] = None
    validator: Optional[Callable[[Any], bool]] = None  # Custom validator
    default_value: Optional[Any] = None
    export_formatter: Optional[Callable[[Any], str]] = None  # Format for export


@dataclass
class EntitySchema:
    """Complete schema for an entity's CSV import/export."""
    table_name: str
    display_name: str
    unique_columns: Tuple[str, ...]  # Columns that define uniqueness
    fields: List[CSVFieldDef]
    post_import_hook: PostImportHook = PostImportHook.NONE
    include_in_export: bool = True  # Whether to include in "Export All"


# ============================================================================
# PURCHASE SCHEMA
# ============================================================================

PURCHASE_SCHEMA = EntitySchema(
    table_name='purchases',
    display_name='Purchases',
    unique_columns=('user_id', 'site_id', 'purchase_date', 'purchase_time'),
    fields=[
        CSVFieldDef('user_id', 'User Name', FieldType.FOREIGN_KEY, required=True,
                    foreign_key=ForeignKeyDef('users', 'id', 'name')),
        CSVFieldDef('site_id', 'Site Name', FieldType.FOREIGN_KEY, required=True,
                    foreign_key=ForeignKeyDef('sites', 'id', 'name')),
        CSVFieldDef('purchase_date', 'Purchase Date', FieldType.DATE, required=True),
        CSVFieldDef('purchase_time', 'Purchase Time', FieldType.TIME, required=False,
                    default_value='00:00:00'),
        CSVFieldDef('amount', 'Amount', FieldType.DECIMAL, required=True,
                    validator=lambda x: float(x) > 0),
        CSVFieldDef('sc_received', 'SC Received', FieldType.DECIMAL, required=True,
                    validator=lambda x: float(x) >= 0),
        CSVFieldDef('starting_sc_balance', 'Post-Purchase SC', FieldType.DECIMAL, required=False),
        CSVFieldDef('cashback_earned', 'Cashback Earned', FieldType.DECIMAL, required=False,
                    default_value='0.00'),
        CSVFieldDef('card_id', 'Card Name', FieldType.FOREIGN_KEY, required=False,
                    foreign_key=ForeignKeyDef('cards', 'id', 'name')),
        CSVFieldDef('notes', 'Notes', FieldType.TEXT, required=False),
    ],
    post_import_hook=PostImportHook.PROMPT_RECALCULATE_EVERYTHING
)


# ============================================================================
# REDEMPTION SCHEMA
# ============================================================================

REDEMPTION_SCHEMA = EntitySchema(
    table_name='redemptions',
    display_name='Redemptions',
    unique_columns=('user_id', 'site_id', 'redemption_date', 'redemption_time'),
    fields=[
        CSVFieldDef('user_id', 'User Name', FieldType.FOREIGN_KEY, required=True,
                    foreign_key=ForeignKeyDef('users', 'id', 'name')),
        CSVFieldDef('site_id', 'Site Name', FieldType.FOREIGN_KEY, required=True,
                    foreign_key=ForeignKeyDef('sites', 'id', 'name')),
        CSVFieldDef('redemption_date', 'Redemption Date', FieldType.DATE, required=True),
        CSVFieldDef('redemption_time', 'Redemption Time', FieldType.TIME, required=False,
                    default_value='00:00:00'),
        CSVFieldDef('amount', 'Amount', FieldType.DECIMAL, required=True,
                    validator=lambda x: float(x) > 0),
        CSVFieldDef('fees', 'Fees', FieldType.DECIMAL, required=False,
                    default_value='0.00'),
        CSVFieldDef('redemption_method_id', 'Method Name', FieldType.FOREIGN_KEY, required=False,
                    foreign_key=ForeignKeyDef('redemption_methods', 'id', 'name')),
        CSVFieldDef('receipt_date', 'Receipt Date', FieldType.DATE, required=False),
        CSVFieldDef('is_free_sc', 'Free SC', FieldType.BOOLEAN, required=False,
                    default_value=0),
        CSVFieldDef('processed', 'Processed', FieldType.BOOLEAN, required=False,
                    default_value=0),
        CSVFieldDef('notes', 'Notes', FieldType.TEXT, required=False),
    ],
    post_import_hook=PostImportHook.PROMPT_RECALCULATE_EVERYTHING
)


# ============================================================================
# GAME SESSION SCHEMA
# ============================================================================

GAME_SESSION_SCHEMA = EntitySchema(
    table_name='game_sessions',
    display_name='Game Sessions',
    unique_columns=('user_id', 'site_id', 'session_date', 'session_time'),
    fields=[
        CSVFieldDef('user_id', 'User Name', FieldType.FOREIGN_KEY, required=True,
                    foreign_key=ForeignKeyDef('users', 'id', 'name')),
        CSVFieldDef('site_id', 'Site Name', FieldType.FOREIGN_KEY, required=True,
                    foreign_key=ForeignKeyDef('sites', 'id', 'name')),
        CSVFieldDef('game_id', 'Game Name', FieldType.FOREIGN_KEY, required=False,
                    foreign_key=ForeignKeyDef('games', 'id', 'name')),
        CSVFieldDef('session_date', 'Session Date', FieldType.DATE, required=True),
        CSVFieldDef('session_time', 'Start Time', FieldType.TIME, required=False,
                    default_value='00:00:00'),
        CSVFieldDef('starting_balance', 'Starting SC', FieldType.DECIMAL, required=True,
                    validator=lambda x: float(x) >= 0),
        CSVFieldDef('ending_balance', 'Ending SC', FieldType.DECIMAL, required=False),
        CSVFieldDef('wager_amount', 'Wager Amount', FieldType.DECIMAL, required=False,
                    default_value='0.00'),
        CSVFieldDef('starting_redeemable', 'Starting Redeemable', FieldType.DECIMAL, required=False),
        CSVFieldDef('ending_redeemable', 'Ending Redeemable', FieldType.DECIMAL, required=False),
        # Note: purchases_during and redemptions_during are CALCULATED fields
        # They are populated during session recalculation and should NOT be imported/exported
        CSVFieldDef('end_date', 'End Date', FieldType.DATE, required=False),
        CSVFieldDef('end_time', 'End Time', FieldType.TIME, required=False),
        CSVFieldDef('notes', 'Notes', FieldType.TEXT, required=False),
    ],
    post_import_hook=PostImportHook.PROMPT_RECALCULATE_EVERYTHING
)


# ============================================================================
# SETUP ENTITY SCHEMAS
# ============================================================================

USER_SCHEMA = EntitySchema(
    table_name='users',
    display_name='Users',
    unique_columns=('name',),
    fields=[
        CSVFieldDef('name', 'User Name', FieldType.TEXT, required=True),
        CSVFieldDef('email', 'Email', FieldType.TEXT, required=False),
        CSVFieldDef('is_active', 'Active', FieldType.BOOLEAN, required=False,
                    default_value=1),
        CSVFieldDef('notes', 'Notes', FieldType.TEXT, required=False),
    ],
    post_import_hook=PostImportHook.NONE
)

SITE_SCHEMA = EntitySchema(
    table_name='sites',
    display_name='Sites',
    unique_columns=('name',),
    fields=[
        CSVFieldDef('name', 'Site Name', FieldType.TEXT, required=True),
        CSVFieldDef('url', 'URL', FieldType.TEXT, required=False),
        CSVFieldDef('sc_rate', 'SC Rate', FieldType.DECIMAL, required=False,
                    default_value='1.0'),
        CSVFieldDef('is_active', 'Active', FieldType.BOOLEAN, required=False,
                    default_value=1),
        CSVFieldDef('notes', 'Notes', FieldType.TEXT, required=False),
    ],
    post_import_hook=PostImportHook.NONE
)

CARD_SCHEMA = EntitySchema(
    table_name='cards',
    display_name='Cards',
    unique_columns=('name', 'user_id'),
    fields=[
        CSVFieldDef('name', 'Card Name', FieldType.TEXT, required=True),
        CSVFieldDef('user_id', 'User Name', FieldType.FOREIGN_KEY, required=True,
                    foreign_key=ForeignKeyDef('users', 'id', 'name')),
        CSVFieldDef('last_four', 'Last 4 Digits', FieldType.TEXT, required=False),
        CSVFieldDef('cashback_rate', 'Cashback Rate', FieldType.DECIMAL, required=False,
                    default_value='0.0'),
        CSVFieldDef('is_active', 'Active', FieldType.BOOLEAN, required=False,
                    default_value=1),
        CSVFieldDef('notes', 'Notes', FieldType.TEXT, required=False),
    ],
    post_import_hook=PostImportHook.NONE
)

REDEMPTION_METHOD_SCHEMA = EntitySchema(
    table_name='redemption_methods',
    display_name='Redemption Methods',
    unique_columns=('name', 'user_id'),
    fields=[
        CSVFieldDef('name', 'Method Name', FieldType.TEXT, required=True),
        CSVFieldDef('method_type', 'Method Type', FieldType.TEXT, required=False),
        CSVFieldDef('user_id', 'User Name', FieldType.FOREIGN_KEY, required=False,
                    foreign_key=ForeignKeyDef('users', 'id', 'name')),
        CSVFieldDef('is_active', 'Active', FieldType.BOOLEAN, required=False,
                    default_value=1),
        CSVFieldDef('notes', 'Notes', FieldType.TEXT, required=False),
    ],
    post_import_hook=PostImportHook.NONE
)

REDEMPTION_METHOD_TYPE_SCHEMA = EntitySchema(
    table_name='redemption_method_types',
    display_name='Redemption Method Types',
    unique_columns=('name',),
    fields=[
        CSVFieldDef('name', 'Method Type Name', FieldType.TEXT, required=True),
        CSVFieldDef('is_active', 'Active', FieldType.BOOLEAN, required=False,
                    default_value=1),
        CSVFieldDef('notes', 'Notes', FieldType.TEXT, required=False),
    ],
    post_import_hook=PostImportHook.NONE
)

GAME_TYPE_SCHEMA = EntitySchema(
    table_name='game_types',
    display_name='Game Types',
    unique_columns=('name',),
    fields=[
        CSVFieldDef('name', 'Game Type', FieldType.TEXT, required=True),
        CSVFieldDef('is_active', 'Active', FieldType.BOOLEAN, required=False,
                    default_value=1),
        CSVFieldDef('notes', 'Notes', FieldType.TEXT, required=False),
    ],
    post_import_hook=PostImportHook.NONE
)

GAME_SCHEMA = EntitySchema(
    table_name='games',
    display_name='Games',
    unique_columns=('name', 'game_type_id'),
    fields=[
        CSVFieldDef('name', 'Game Name', FieldType.TEXT, required=True),
        CSVFieldDef('game_type_id', 'Game Type', FieldType.FOREIGN_KEY, required=True,
                    foreign_key=ForeignKeyDef('game_types', 'id', 'name')),
        CSVFieldDef('rtp', 'RTP', FieldType.DECIMAL, required=False),
        CSVFieldDef('is_active', 'Active', FieldType.BOOLEAN, required=False,
                    default_value=1),
        CSVFieldDef('notes', 'Notes', FieldType.TEXT, required=False),
    ],
    post_import_hook=PostImportHook.NONE
)


# ============================================================================
# SCHEMA REGISTRY
# ============================================================================

SCHEMA_REGISTRY = {
    'purchases': PURCHASE_SCHEMA,
    'redemptions': REDEMPTION_SCHEMA,
    'game_sessions': GAME_SESSION_SCHEMA,
    'users': USER_SCHEMA,
    'sites': SITE_SCHEMA,
    'cards': CARD_SCHEMA,
    'redemption_methods': REDEMPTION_METHOD_SCHEMA,
    'redemption_method_types': REDEMPTION_METHOD_TYPE_SCHEMA,
    'game_types': GAME_TYPE_SCHEMA,
    'games': GAME_SCHEMA,
}


def get_schema(entity_type: str) -> EntitySchema:
    """Get schema for an entity type.
    
    Args:
        entity_type: Entity type name (e.g., 'purchases', 'users')
    
    Returns:
        EntitySchema for the entity type
    
    Raises:
        KeyError: If entity type not found
    """
    if entity_type not in SCHEMA_REGISTRY:
        raise KeyError(f"Unknown entity type: {entity_type}")
    return SCHEMA_REGISTRY[entity_type]


def get_all_schemas() -> List[EntitySchema]:
    """Get all registered entity schemas."""
    return list(SCHEMA_REGISTRY.values())


def get_exportable_schemas() -> List[EntitySchema]:
    """Get schemas that should be included in 'Export All' operations."""
    return [schema for schema in SCHEMA_REGISTRY.values() if schema.include_in_export]
