import json
import subprocess
import time
from typing import TypedDict, List
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.CopyToClipboardAction import CopyToClipboardAction
from fuzzyfinder import fuzzyfinder


class TailscaleNode(TypedDict):
    hostname: str
    ipv4: str
    online: bool


class TailscaleExtension(Extension):
    def __init__(self):
        super().__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener(self))
        self._cache_nodes: List[TailscaleNode] = []
        self._cache_timestamp: float = 0
        self._cache_duration: int = 10  # 10 seconds

    def _list_nodes(self) -> List[TailscaleNode]:
        try:
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True,
                text=True,
                check=True,
            )

            status = json.loads(result.stdout)
            nodes = []

            # Add self node
            if "Self" in status:
                self_node = status["Self"]
                ipv4 = next((ip for ip in self_node["TailscaleIPs"] if "." in ip), "")
                if ipv4:
                    nodes.append(
                        {
                            "hostname": self_node["HostName"],
                            "ipv4": ipv4,
                            "online": self_node["Online"],
                        }
                    )

            # Add peer nodes
            if "Peer" in status:
                for peer in status["Peer"].values():
                    ipv4 = next((ip for ip in peer["TailscaleIPs"] if "." in ip), "")
                    if ipv4:
                        nodes.append(
                            {
                                "hostname": peer["HostName"],
                                "ipv4": ipv4,
                                "online": peer["Online"],
                            }
                        )

            return nodes
        except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
            return []

    def list_nodes(self) -> List[TailscaleNode]:
        current_time = time.time()

        # Check if cache is still valid (within 10 seconds)
        if current_time - self._cache_timestamp < self._cache_duration:
            return self._cache_nodes

        # Cache is expired, refresh it
        self._cache_nodes = self._list_nodes()
        self._cache_timestamp = current_time

        return self._cache_nodes


class KeywordQueryEventListener(EventListener):
    extension: TailscaleExtension

    def __init__(self, extension):
        super().__init__()
        self.extension = extension

    def on_event(self, event, _):  # type: ignore
        limit = int(self.extension.preferences.get("limit", "9"))
        query = event.get_argument() or ""

        nodes: list[TailscaleNode] = list(
            fuzzyfinder(
                query,
                self.extension.list_nodes(),
                accessor=lambda node: node["hostname"],
            )
        )[:limit]

        items = [
            ExtensionResultItem(
                icon="images/tailscale-appicon.png",
                name=f"{node["hostname"]}{"" if node["online"] else " (offline)"}",
                description=node["ipv4"],
                on_enter=CopyToClipboardAction(node["ipv4"]),
            )
            for node in nodes
        ]

        return RenderResultListAction(items)


if __name__ == "__main__":
    TailscaleExtension().run()
