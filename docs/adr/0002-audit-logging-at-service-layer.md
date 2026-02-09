# ADR 0002: Audit Logging at Service Layer (Not AppFacade)

**Date:** 2026-02-09  
**Status:** Accepted  
**Issue:** #92 - Audit Log + Undo/Redo + Soft Delete

## Context

Issue #92 specified a preference for audit logging to happen "at a single orchestration layer (prefer `AppFacade`)" to avoid scattering concerns across UI/services/repositories.

During implementation, we faced a design choice:
1. **Centralized approach**: AppFacade intercepts all CRUD operations and logs audits
2. **Distributed approach**: Each service logs its own audits at the method level

## Decision

We chose the **distributed approach**: audit logging happens at the service layer, with each service (`PurchaseService`, `RedemptionService`, `GameSessionService`) calling `audit_service.log_create/update/delete()` directly within their CRUD methods.

## Rationale

### Why Service Layer vs AppFacade:

1. **Atomicity guarantees**:
   - Services already own the transactional boundary for their operations
   - Audit logging needs to be atomic with the mutation it describes
   - Placing audit calls in services ensures they're inside the same transaction as the data change
   - If audit logging were in AppFacade, it would require careful coordination to ensure atomicity

2. **Simplicity and maintainability**:
   - Each service knows exactly what changed (old vs new state)
   - Services can capture `old_data` immediately after fetching from repository
   - No need for complex introspection or snapshot diffing at facade layer
   - Clear ownership: if you modify a service method, you update its audit logging

3. **Type safety**:
   - Services work with domain models (Purchase, Redemption, GameSession)
   - `asdict()` conversion happens once per operation
   - AppFacade would need to handle heterogeneous types or use reflection

4. **Flexibility**:
   - Different entities may have different audit requirements
   - Service layer can customize what gets logged (e.g., excluding sensitive fields)
   - Bulk operations can use `group_id` to link related audits

### Trade-offs Accepted:

**Con**: Audit logging is distributed across three services instead of centralized
- **Mitigation**: All services use the same `AuditService` API, ensuring consistency
- **Mitigation**: Pattern is documented and enforced by tests (all CRUD operations must log)

**Con**: Risk of missing audit calls when adding new CRUD methods
- **Mitigation**: Test suite verifies audit coverage (787/787 tests passing)
- **Mitigation**: Code review checklist includes "Does this need audit logging?"

## Implementation Pattern

Services capture audit data using this pattern:

```python
# UPDATE example
def update_entity(self, entity_id: int, **kwargs):
    entity = self.repo.get_by_id(entity_id)
    
    # Capture BEFORE modifications
    old_data = asdict(entity)
    
    # Apply changes
    for key, value in kwargs.items():
        setattr(entity, key, value)
    
    # Persist
    result = self.repo.update(entity)
    
    # Log atomically (within same transaction if applicable)
    if self.audit_service:
        self.audit_service.log_update('table', entity.id, old_data, asdict(result))
    
    return result
```

**Key characteristics:**
- `old_data` captured immediately after fetch (before mutations)
- `audit_service` is optional (injected via property, not constructor)
- `auto_commit=True` by default; services can use `auto_commit=False` for explicit transaction management
- Bulk operations use `group_id` to link related audits

## Consequences

### Positive:
- ✅ Simple, clear ownership of audit logging
- ✅ Atomic logging guaranteed by transaction boundaries
- ✅ Type-safe, no reflection needed
- ✅ Flexible per-entity customization

### Negative:
- ⚠️ Audit logging code appears in multiple places
- ⚠️ Requires discipline when adding new CRUD methods

### Neutral:
- Services have dependency on `AuditService` (injected post-construction in `AppFacade`)

## Alternatives Considered

### Alternative 1: AppFacade interception
**Approach**: AppFacade wraps all service calls and logs before/after
**Rejected because**:
- Would require sophisticated snapshot/diff logic
- Hard to determine what changed without introspecting service internals
- Breaks transaction atomicity (facade operates outside service transaction)

### Alternative 2: Repository-layer hooks
**Approach**: Repositories automatically log all changes
**Rejected because**:
- Repositories don't understand business semantics (what's a "create purchase" vs a "restore purchase"?)
- Would need to pass context down through all repository calls
- Violates single responsibility (repositories should focus on data access)

### Alternative 3: Aspect-Oriented Programming / Decorators
**Approach**: Use Python decorators to auto-inject audit logging
**Rejected because**:
- Still requires per-method application (same distribution as current approach)
- Harder to debug (magic behavior)
- Difficult to customize per-entity

## References

- Issue #92: Feature request for centralized audit logging
- `services/audit_service.py`: Shared audit API
- `app_facade.py` lines 201-204: Audit service injection into services
- Commit 1e8b2f4: "Fix missing imports and return statement - all 787 tests passing (Issue #92)"
