from scholar_flux.api.models.provider_registry import ProviderRegistry
from types import MappingProxyType

# creates an object that can be overriden to add new mappings of provider names to provider configs
provider_registry = ProviderRegistry.from_defaults()

# create a separate immutable mapping of the same providers
PROVIDER_DEFAULTS = MappingProxyType(provider_registry.copy())

