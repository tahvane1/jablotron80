"""Errors for the Jablotron component."""
from homeassistant.exceptions import HomeAssistantError


class JablotronException(HomeAssistantError):
	"""Base class for Jablotron exceptions."""


class ServiceUnavailable(JablotronException):
	"""Service is not available."""



class ModelNotSupported(JablotronException):
	"""Model not supported."""


class ShouldNotHappen(JablotronException):
	"""This should not happen."""
