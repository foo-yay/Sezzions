"""
Database Backup Service

Provides safe database backup operations using SQLite's online backup API.
Supports backing up while the application is running without closing connections.
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

from services.tools.dtos import BackupResult
from services.tools.enums import RestoreMode


class BackupService:
    """
    Service for creating database backups.
    
    Uses SQLite's online backup API for consistent backups while app is running.
    Handles file operations safely with rollback on errors.
    """
    
    def __init__(self, db_connection):
        """
        Initialize backup service.
        
        Args:
            db_connection: Active database connection
        """
        self.db = db_connection
    
    def backup_database(
        self,
        backup_path: str,
        include_audit_log: bool = True,
        compress: bool = False
    ) -> BackupResult:
        """
        Create full database backup using SQLite online backup API.
        
        This method creates a consistent backup without closing the source database.
        The backup occurs while the application continues to run.
        
        Args:
            backup_path: Destination file path for backup
            include_audit_log: Whether to include audit_log table (default True)
            compress: Whether to compress backup (future feature, default False)
        
        Returns:
            BackupResult with success status, file path, and size
        
        Example:
            >>> service = BackupService(db)
            >>> result = service.backup_database('backups/backup_20260127.db')
            >>> print(f"Backup size: {result.size_bytes / 1024:.1f} KB")
        """
        backup_path_obj = Path(backup_path)
        
        try:
            # Ensure backup directory exists
            backup_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if backup file already exists
            if backup_path_obj.exists():
                return BackupResult(
                    success=False,
                    error=f"Backup file already exists: {backup_path}"
                )
            
            # Use SQLite online backup API
            # This copies the database page-by-page while allowing concurrent access
            src_conn = self._get_connection()
            dest_conn = sqlite3.connect(str(backup_path))
            
            try:
                # Perform the backup
                src_conn.backup(dest_conn)
                
                # Optionally exclude audit log
                if not include_audit_log:
                    dest_cursor = dest_conn.cursor()
                    dest_cursor.execute("DELETE FROM audit_log")
                    dest_conn.commit()
                
                dest_conn.close()
                
                # Get backup file size
                size_bytes = backup_path_obj.stat().st_size
                
                # Log audit trail
                self.db.log_audit(
                    action='BACKUP',
                    table_name='database',
                    details=f"Backup created: {backup_path} ({size_bytes:,} bytes)"
                )
                
                return BackupResult(
                    success=True,
                    backup_path=str(backup_path),
                    size_bytes=size_bytes
                )
                
            except Exception as e:
                dest_conn.close()
                # Clean up failed backup file
                if backup_path_obj.exists():
                    backup_path_obj.unlink()
                raise e
                
        except Exception as e:
            return BackupResult(
                success=False,
                error=f"Backup failed: {str(e)}"
            )
    
    def backup_with_timestamp(
        self,
        backup_dir: str,
        prefix: str = "backup",
        include_audit_log: bool = True
    ) -> BackupResult:
        """
        Create timestamped backup file.
        
        Generates filename: {prefix}_YYYYMMDD_HHMMSS.db
        
        Args:
            backup_dir: Directory for backup file
            prefix: Filename prefix (default "backup")
            include_audit_log: Whether to include audit log
        
        Returns:
            BackupResult with success status and file info
        
        Example:
            >>> result = service.backup_with_timestamp('backups/')
            >>> # Creates: backups/backup_20260127_143052.db
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.db"
        backup_path = Path(backup_dir) / filename
        
        return self.backup_database(
            backup_path=str(backup_path),
            include_audit_log=include_audit_log
        )
    
    def list_backups(self, backup_dir: str, prefix: str = "backup") -> list[dict]:
        """
        List all backup files in directory.
        
        Args:
            backup_dir: Directory to search
            prefix: Filename prefix to filter (default "backup")
        
        Returns:
            List of backup info dicts with: path, timestamp, size_bytes
        
        Example:
            >>> backups = service.list_backups('backups/')
            >>> for backup in backups:
            ...     print(f"{backup['timestamp']}: {backup['size_bytes']} bytes")
        """
        backup_dir_path = Path(backup_dir)
        
        if not backup_dir_path.exists():
            return []
        
        backups = []
        pattern = f"{prefix}_*.db"
        
        for backup_file in sorted(backup_dir_path.glob(pattern), reverse=True):
            try:
                stat = backup_file.stat()
                backups.append({
                    'path': str(backup_file),
                    'filename': backup_file.name,
                    'timestamp': datetime.fromtimestamp(stat.st_mtime),
                    'size_bytes': stat.st_size
                })
            except Exception:
                # Skip files we can't read
                continue
        
        return backups
    
    def delete_old_backups(
        self,
        backup_dir: str,
        keep_count: int = 10,
        prefix: str = "backup"
    ) -> int:
        """
        Delete old backup files, keeping only the most recent N backups.
        
        Args:
            backup_dir: Directory containing backups
            keep_count: Number of recent backups to keep (default 10)
            prefix: Filename prefix to filter (default "backup")
        
        Returns:
            Number of backup files deleted
        
        Example:
            >>> deleted = service.delete_old_backups('backups/', keep_count=5)
            >>> print(f"Deleted {deleted} old backups")
        """
        backups = self.list_backups(backup_dir, prefix)
        
        if len(backups) <= keep_count:
            return 0
        
        # Delete oldest backups beyond keep_count
        to_delete = backups[keep_count:]
        deleted_count = 0
        
        for backup in to_delete:
            try:
                Path(backup['path']).unlink()
                deleted_count += 1
            except Exception:
                # Skip files we can't delete
                continue
        
        return deleted_count
    
    def verify_backup(self, backup_path: str) -> BackupResult:
        """
        Verify backup file integrity.
        
        Opens backup database and runs PRAGMA integrity_check.
        
        Args:
            backup_path: Path to backup file to verify
        
        Returns:
            BackupResult with success=True if backup is valid
        
        Example:
            >>> result = service.verify_backup('backups/backup_20260127.db')
            >>> if result.success:
            ...     print("Backup is valid")
        """
        backup_path_obj = Path(backup_path)
        
        if not backup_path_obj.exists():
            return BackupResult(
                success=False,
                error=f"Backup file not found: {backup_path}"
            )
        
        try:
            # Open backup database
            conn = sqlite3.connect(str(backup_path))
            cursor = conn.cursor()
            
            # Run integrity check
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            
            conn.close()
            
            if result and result[0] == 'ok':
                size_bytes = backup_path_obj.stat().st_size
                return BackupResult(
                    success=True,
                    backup_path=str(backup_path),
                    size_bytes=size_bytes
                )
            else:
                return BackupResult(
                    success=False,
                    error=f"Integrity check failed: {result[0] if result else 'unknown error'}"
                )
                
        except Exception as e:
            return BackupResult(
                success=False,
                error=f"Verification failed: {str(e)}"
            )
    
    def _get_connection(self):
        """
        Get underlying SQLite connection.
        
        Handles different connection wrapper types.
        """
        # Handle different database wrapper types
        if hasattr(self.db, '_connection'):
            return self.db._connection
        elif hasattr(self.db, 'conn'):
            return self.db.conn
        else:
            # Assume it's already a connection
            return self.db
