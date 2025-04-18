from luthien_control.db.models import ClientApiKey, Policy
from luthien_control.db.sqlmodel_models import ClientApiKey as SqlModelClientApiKey
from luthien_control.db.sqlmodel_models import Policy as SqlModelPolicy


def convert_api_key_to_sqlmodel(legacy_api_key: ClientApiKey) -> SqlModelClientApiKey:
    return SqlModelClientApiKey(
        id=legacy_api_key.id,
        key_value=legacy_api_key.key_value,
        name=legacy_api_key.name,
        is_active=legacy_api_key.is_active,
        created_at=legacy_api_key.created_at,
        metadata_=legacy_api_key.metadata_,
    )


def convert_policy_to_sqlmodel(legacy_policy: Policy) -> SqlModelPolicy:
    return SqlModelPolicy(
        id=legacy_policy.id,
        name=legacy_policy.name,
        policy_class_path=legacy_policy.policy_class_path,
        config=legacy_policy.config,
        is_active=legacy_policy.is_active,
        description=legacy_policy.description,
        created_at=legacy_policy.created_at,
        updated_at=legacy_policy.updated_at,
    )
