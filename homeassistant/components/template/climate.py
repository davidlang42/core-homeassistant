"""Support for Template climate entities."""
import logging

import voluptuous as vol

from homeassistant.components.climate import ENTITY_ID_FORMAT, ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    CURRENT_HVAC_ACTIONS,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    FAN_MODES,
    HVAC_MODES,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.script import Script

from .const import CONF_AVAILABILITY_TEMPLATE
from .template_entity import TemplateEntity

_LOGGER = logging.getLogger(__name__)

CONF_CLIMATES = "climates"
CONF_HVAC_ACTION_TEMPLATE = "hvac_action_template"
CONF_SET_HVAC_MODE_ACTION = "set_hvac_mode"
CONF_HVAC_MODES = "hvac_modes"
CONF_SET_FAN_MODE_ACTION = "set_fan_mode"
CONF_FAN_MODES = "fan_modes"
CONF_FAN_MODE_TEMPLATE = "fan_mode_template"
CONF_SET_TEMPERATURE_ACTION = "set_temperature"
CONF_TEMPERATURE_TEMPLATE = "temperature_template"
CONF_CURRENT_TEMPERATURE_TEMPLATE = "current_temperature_template"
CONF_TEMPERATURE_STEP = "temperature_step"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_PRECISION = "precision"

CLIMATE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Required(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_HVAC_ACTION_TEMPLATE): cv.template,
        vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
        vol.Required(CONF_SET_HVAC_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_HVAC_MODES, default=HVAC_MODES): vol.All(
            cv.ensure_list, [vol.In(HVAC_MODES)]
        ),
        vol.Optional(CONF_SET_FAN_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_FAN_MODES, default=FAN_MODES): cv.ensure_list,
        vol.Optional(CONF_FAN_MODE_TEMPLATE): cv.template,
        vol.Optional(CONF_SET_TEMPERATURE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_TEMPERATURE_TEMPLATE): cv.template,
        vol.Optional(CONF_CURRENT_TEMPERATURE_TEMPLATE): cv.template,
        vol.Optional(CONF_TEMPERATURE_STEP): vol.Coerce(float),
        vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
        vol.Optional(CONF_PRECISION): vol.In(
            [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
        ),
        vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_CLIMATES): cv.schema_with_slug_keys(CLIMATE_SCHEMA)}
)


async def _async_create_entities(hass, config):
    """Create the Template Climates."""
    climates = []

    for device, device_config in config[CONF_CLIMATES].items():
        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)

        state_template = device_config[CONF_VALUE_TEMPLATE]
        hvac_action_template = device_config.get(CONF_HVAC_ACTION_TEMPLATE)
        availability_template = device_config.get(CONF_AVAILABILITY_TEMPLATE)
        fan_mode_template = device_config.get(CONF_FAN_MODE_TEMPLATE)
        temperature_template = device_config.get(CONF_TEMPERATURE_TEMPLATE)
        current_temperature_template = device_config.get(
            CONF_CURRENT_TEMPERATURE_TEMPLATE
        )

        set_hvac_mode_action = device_config[CONF_SET_HVAC_MODE_ACTION]
        set_fan_mode_action = device_config.get(CONF_SET_FAN_MODE_ACTION)
        set_temperature_action = device_config.get(CONF_SET_TEMPERATURE_ACTION)

        hvac_modes = device_config.get(CONF_HVAC_MODES)
        fan_modes = device_config.get(CONF_FAN_MODES)
        temperature_step = device_config.get(CONF_TEMPERATURE_STEP)
        min_temp = device_config.get(CONF_MIN_TEMP)
        max_temp = device_config.get(CONF_MAX_TEMP)
        precision = device_config.get(CONF_PRECISION)
        unique_id = device_config.get(CONF_UNIQUE_ID)

        climates.append(
            TemplateClimate(
                hass,
                device,
                friendly_name,
                state_template,
                hvac_action_template,
                availability_template,
                set_hvac_mode_action,
                hvac_modes,
                set_fan_mode_action,
                fan_modes,
                fan_mode_template,
                set_temperature_action,
                temperature_template,
                current_temperature_template,
                temperature_step,
                min_temp,
                max_temp,
                precision,
                unique_id,
            )
        )

    return climates


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the template climates."""
    async_add_entities(await _async_create_entities(hass, config))


class TemplateClimate(TemplateEntity, ClimateEntity):
    """A template climate component."""

    def __init__(
        self,
        hass,
        device_id,
        friendly_name,
        state_template,
        hvac_action_template,
        availability_template,
        set_hvac_mode_action,
        hvac_modes,
        set_fan_mode_action,
        fan_modes,
        fan_mode_template,
        set_temperature_action,
        temperature_template,
        current_temperature_template,
        temperature_step,
        min_temp,
        max_temp,
        precision,
        unique_id,
    ):
        """Initialize the climate."""
        super().__init__(availability_template=availability_template)
        self.hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )
        self._attr_name = friendly_name

        self._template = state_template
        self._hvac_action_template = hvac_action_template
        self._fan_mode_template = fan_mode_template
        self._temperature_template = temperature_template
        self._current_temperature_template = current_temperature_template
        self._attr_supported_features = 0

        domain = __name__.split(".")[-2]

        self._set_hvac_mode_script = Script(
            hass, set_hvac_mode_action, friendly_name, domain
        )

        self._set_fan_mode_script = None
        if set_fan_mode_action:
            self._set_fan_mode_script = Script(
                hass, set_fan_mode_action, friendly_name, domain
            )
            self._attr_supported_features |= SUPPORT_FAN_MODE

        self._set_temperature_script = None
        if set_temperature_action:
            self._set_temperature_script = Script(
                hass, set_temperature_action, friendly_name, domain
            )
            self._attr_supported_features |= SUPPORT_TARGET_TEMPERATURE

        self._attr_state = None
        self._attr_hvac_action = None
        self._attr_fan_mode = None
        self._attr_target_temperature = None
        self._attr_current_temperature = None

        self._attr_unique_id = unique_id
        self._attr_temperature_unit = hass.config.units.temperature_unit

        self._attr_hvac_modes = hvac_modes
        self._attr_fan_modes = fan_modes
        self._attr_target_temperature_step = temperature_step
        self._attr_precision = precision
        self._attr_min_temp = min_temp
        self._attr_max_temp = max_temp

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode not in self.hvac_modes:
            _LOGGER.error(
                "Received invalid hvac_mode: %s. Expected: %s",
                hvac_mode,
                self.hvac_modes,
            )
            return

        self._attr_state = hvac_mode

        await self._set_hvac_mode_script.async_run(
            {ATTR_HVAC_MODE: hvac_mode}, context=self._context
        )

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        if fan_mode not in self.fan_modes:
            _LOGGER.error(
                "Received invalid fan_mode: %s. Expected: %s", fan_mode, self.fan_modes
            )
            return

        self._attr_fan_mode = fan_mode

        if self._set_fan_mode_script:
            await self._set_fan_mode_script.async_run(
                {ATTR_FAN_MODE: fan_mode}, context=self._context
            )

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        if temperature > self.max_temp or temperature < self.min_temp:
            _LOGGER.error(
                "Received invalid temperature: %s. Expected: %s-%s",
                temperature,
                self.min_temp,
                self.max_temp,
            )
            return

        self._attr_target_temperature = temperature

        if self._set_temperature_script:
            await self._set_temperature_script.async_run(
                {ATTR_TEMPERATURE: temperature}, context=self._context
            )

    @callback
    def _update_state(self, result):
        super()._update_state(result)
        if isinstance(result, TemplateError):
            self._attr_state = None
        elif result in self.hvac_modes:
            self._attr_state = result
        elif result in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            self._attr_state = None
        else:
            _LOGGER.error(
                "Received invalid state: %s. Expected: %s",
                result,
                ", ".join(self.hvac_modes),
            )
            self._attr_state = None

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.add_template_attribute("_state", self._template, None, self._update_state)

        if self._hvac_action_template is not None:
            self.add_template_attribute(
                "_hvac_action",
                self._hvac_action_template,
                None,
                self._update_hvac_action,
                none_on_template_error=True,
            )

        if self._fan_mode_template is not None:
            self.add_template_attribute(
                "_fan_mode",
                self._fan_mode_template,
                None,
                self._update_fan_mode,
                none_on_template_error=True,
            )

        if self._temperature_template is not None:
            self.add_template_attribute(
                "_temperature",
                self._temperature_template,
                None,
                self._update_temperature,
                none_on_template_error=True,
            )

        if self._current_temperature_template is not None:
            self.add_template_attribute(
                "_current_temperature",
                self._current_temperature_template,
                None,
                self._update_current_temperature,
                none_on_template_error=True,
            )

        await super().async_added_to_hass()

    @callback
    def _update_hvac_action(self, hvac_action):
        if hvac_action in CURRENT_HVAC_ACTIONS:
            self._attr_hvac_action = hvac_action
        elif hvac_action in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            self._attr_hvac_action = None
        else:
            _LOGGER.error(
                "Received invalid hvac_action: %s. Expected: %s",
                hvac_action,
                CURRENT_HVAC_ACTIONS,
            )
            self._attr_hvac_action = None

    @callback
    def _update_fan_mode(self, fan_mode):
        if fan_mode in self.fan_modes:
            self._attr_fan_mode = fan_mode
        elif fan_mode in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            self._attr_fan_mode = None
        else:
            _LOGGER.error(
                "Received invalid hvac_action: %s. Expected: %s",
                fan_mode,
                self.fan_modes,
            )
            self._attr_fan_mode = None

    @callback
    def _update_temperature(self, temperature):
        if self.min_temp <= temperature <= self.max_temp:
            self._attr_target_temperature = temperature
        elif temperature in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            self._attr_target_temperature = None
        else:
            _LOGGER.error(
                "Received invalid temperature: %s. Expected: %s-%s",
                temperature,
                self.min_temp,
                self.max_temp,
            )
            self._attr_target_temperature = None

    @callback
    def _update_current_temperature(self, current_temperature):
        if current_temperature in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            self._attr_current_temperature = None
            return
        try:
            if self.min_temp > float(current_temperature) > self.max_temp:
                raise ValueError("Out of range")
            self._attr_current_temperature = current_temperature
        except ValueError:
            _LOGGER.error(
                "Received invalid current temperature: %s. Expected: %s-%s",
                current_temperature,
                self.min_temp,
                self.max_temp,
            )
            self._attr_current_temperature = None
