"""Handle KNX project data."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from xknx.dpt import DPTBase
from xknxproject import XKNXProj
from xknxproject.models import (
    Device,
    GroupAddress as GroupAddressModel,
    KNXProject as KNXProjectModel,
    ProjectInfo,
)

from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = f"{DOMAIN}/knx_project.json"


@dataclass
class GroupAddressInfo:
    """Group address info for runtime usage."""

    address: str
    name: str
    description: str
    dpt_main: int | None
    dpt_sub: int | None
    transcoder: type[DPTBase] | None


class KNXProject:
    """Manage KNX project data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize project data."""
        self.hass = hass
        self._store = Store[KNXProjectModel](hass, STORAGE_VERSION, STORAGE_KEY)

        self.loaded: bool
        self.devices: dict[str, Device]
        self.group_addresses: dict[str, GroupAddressInfo]
        self.info: ProjectInfo | None

        self.initial_state()

    def initial_state(self) -> None:
        """Set initial state for project data."""
        self.loaded = False
        self.devices = {}
        self.group_addresses = {}
        self.info = None

    async def load_project(self) -> None:
        """Load project data from storage."""
        if project := await self._store.async_load():
            self.devices = project["devices"]
            self.info = project["info"]

            for _ga_model in project["group_addresses"].values():
                ga_info = self._create_group_address_info(_ga_model)
                self.group_addresses[ga_info.address] = ga_info

            self.loaded = True

    def _create_group_address_info(
        self, ga_model: GroupAddressModel
    ) -> GroupAddressInfo:
        """Add items to GroupAddressModel values."""
        dpt = ga_model["dpt"]
        transcoder = (
            DPTBase.transcoder_by_dpt(dpt["main"], dpt.get("sub")) if dpt else None
        )
        return GroupAddressInfo(
            address=ga_model["address"],
            name=ga_model["name"],
            description=ga_model["description"],
            transcoder=transcoder,
            dpt_main=dpt["main"] if dpt else None,
            dpt_sub=dpt["sub"] if dpt else None,
        )

    async def process_project_file(self, file_id: str, password: str) -> None:
        """Process an uploaded project file."""

        def _parse_project() -> KNXProjectModel:
            with process_uploaded_file(self.hass, file_id) as file_path:
                xknxproj = XKNXProj(
                    file_path,
                    password=password,
                    language=self.hass.config.language,
                )
                return xknxproj.parse()

        project = await self.hass.async_add_executor_job(_parse_project)

        await self._store.async_save(project)
        await self.load_project()

    async def remove_project_file(self) -> None:
        """Remove project file from storage."""
        await self._store.async_remove()
        self.initial_state()
