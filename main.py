import json
import subprocess
import time
from typing import TypedDict, List
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.CopyToClipboardAction import CopyToClipboardAction
from ulauncher.api.shared.action.DoNothingAction import DoNothingAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from fuzzyfinder import fuzzyfinder


class TailscaleNode(TypedDict):
    hostname: str
    ipv4: str
    online: bool


class TailscaleExtension(Extension):
    def __init__(self):
        super().__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener(self))
        self.subscribe(ItemEnterEvent, ItemEnterEventListener(self))
        self._cache_nodes: List[TailscaleNode] = []
        self._cache_timestamp: float = 0
        self._cache_duration: int = 10
        self.online = False
        self.check_online()

    def _list_nodes(self) -> List[TailscaleNode]:
        try:
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True,
                text=True,
                check=True,
            )

            status = json.loads(result.stdout)
            nodes: List[TailscaleNode] = []

            def add_node(node):
                nodes.append(
                    {
                        "hostname": node["HostName"],
                        "ipv4": next(
                            (ip for ip in node["TailscaleIPs"] if "." in ip), ""
                        ),
                        "online": node["Online"],
                    }
                )

            # Demo Code
            # add_node({ "HostName": "laptop", "TailscaleIPs": ["100.102.11.93"], "Online": True })
            # add_node({ "HostName": "desktop", "TailscaleIPs": ["100.96.204.133"], "Online": True })
            # add_node({ "HostName": "raspberry-pi", "TailscaleIPs": ["100.79.64.12"], "Online": False })
            # add_node({ "HostName": "router", "TailscaleIPs": ["100.115.81.24"], "Online": True })
            # add_node({ "HostName": "nas", "TailscaleIPs": ["100.103.105.243"], "Online": True })
            # add_node({ "HostName": "cloud-server", "TailscaleIPs": ["100.72.94.105"], "Online": True })

            # Add self node
            add_node(status["Self"])
            self.online = status["Self"]["Online"]

            # Add peer nodes
            for peer in status["Peer"].values():
                add_node(peer)

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

    def handle_toggle_action(self, query: str | None):
        try:
            if self.online:
                subprocess.run(["tailscale", "down"], check=True)
            else:
                subprocess.run(["tailscale", "up"], check=True)
        except subprocess.CalledProcessError:
            pass

        print(f"b4 {self.online}")
        time.sleep(1)
        self.check_online()
        print(f"a4 {self.online}")
        return self.render(query)

    def check_online(self):
        try:
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True,
                text=True,
                check=True,
            )

            status = json.loads(result.stdout)
            self.online = status["Self"]["Online"]
        except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
            return False

    def render(self, query: str | None):
        limit = int(self.preferences.get("limit", "9"))

        all = [
            ExtensionResultItem(
                icon=f"images/{'online' if self.online else 'offline'}.png",
                name="Status",
                description=f"You're {'Online' if self.online else 'Offline'}",
                on_enter=ExtensionCustomAction(
                    {"action": "toggle", "query": query}, True
                ),
                keyword="status",
            )
        ] + [
            ExtensionResultItem(
                icon="images/tailscale.png",
                name=f"{node["hostname"]}{"" if node["online"] else " (offline)"}",
                description=node["ipv4"],
                on_enter=CopyToClipboardAction(node["ipv4"]),
                keyword=node["hostname"],
            )
            for node in self.list_nodes()
        ]

        if not query:
            return RenderResultListAction(all[:limit])

        items: list[ExtensionResultItem] = list(
            fuzzyfinder(
                query,
                all,
                accessor=lambda item: item.get_keyword(),
            )
        )[:limit]

        return RenderResultListAction(items)


class KeywordQueryEventListener(EventListener):
    extension: TailscaleExtension

    def __init__(self, extension):
        super().__init__()
        self.extension = extension

    def on_event(self, event: KeywordQueryEvent, _):  # type: ignore
        return self.extension.render(event.get_argument())


class ItemEnterEventListener(EventListener):
    extension: TailscaleExtension

    def __init__(self, extension):
        super().__init__()
        self.extension = extension

    def on_event(self, event: ItemEnterEvent, _):  # type: ignore
        data = event.get_data()
        if data and data.get("action") == "toggle":
            return self.extension.handle_toggle_action(data.get("query"))

        return DoNothingAction()


if __name__ == "__main__":
    TailscaleExtension().run()
