import argparse
import logging
import os
import sys
import time
import signal
import typing as t

import requests


def add_env_arg(parser: argparse.ArgumentParser, env: str, *, default=None, help: t.Optional[str] = None, type=str):
    help = help or ""
    default = os.environ.get(env) or default
    long = "--" + env.lower().replace("_", "-")
    parser.add_argument(
        long,
        default=default,
        required=default is None,
        help=f"{help} (from ${env}, currently {default}",
        type=type,
    )


class Dingus:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.session = requests.Session()
        self.last_grid_state: t.Optional[str] = None
        self.log = logging.getLogger("envoy-homebridge-dummy")
        self.refresh_interval = args.interval * 6
        self.next_refresh = time.monotonic() + self.refresh_interval

    def run_once(self):
        response = self.session.get(self.args.envoyproxy_url)
        response.raise_for_status()
        response = response.json()
        grid_state = response.get("grid_state")
        if grid_state is None:
            self.log.warn("This system doesn't have a meter collar")
            return
        if grid_state != self.last_grid_state:
            self.log.info("Grid state transititions to %s", grid_state)
            self.send_notification(grid_state)
            self.last_grid_state = grid_state
            self.next_refresh = time.monotonic() + self.refresh_interval
        elif time.monotonic() >= self.next_refresh and self.last_grid_state is not None:
            self.log.info("Sending refresh for %s", self.last_grid_state)
            self.send_notification(self.last_grid_state)
            self.next_refresh = time.monotonic() + self.refresh_interval

    def send_notification(self, state: str):
        value = state in ["on-grid", "multimode-ongrid"]
        self.session.post(
            self.args.homebridge_webhook_url,
            json={"id": self.args.homebridge_accessory_id, "set": "On", "value": value},
        ).raise_for_status()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    add_env_arg(parser, "INTERVAL", help="How often to poll", default=10, type=float)
    add_env_arg(parser, "ENVOYPROXY_URL", help="Base URL for envoyproxy install")
    add_env_arg(parser, "HOMEBRIDGE_ACCESSORY_ID", help="ID for homebridge-dummy switch")
    add_env_arg(parser, "HOMEBRIDGE_WEBHOOK_URL", help="URL to send webhooks to")
    args = parser.parse_args()

    logging.basicConfig(
        stream=sys.stderr,
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    log = logging.getLogger("envoy-homebridge-dummy")

    dingus = Dingus(args)

    running = [True]

    def stop(*args):
        log.info("Shutting down")
        running[0] = False

    for sig in (signal.SIGINT, signal.SIGQUIT, signal.SIGTERM):
        signal.signal(sig, stop)

    while running[0]:
        log.debug("running control loop")
        next_target = time.monotonic() + args.interval
        try:
            dingus.run_once()
        except Exception as exc:
            log.exception(f"Error in loop: {exc}")
        now = time.monotonic()
        while now < next_target and running[0]:
            time.sleep(min(1, next_target - now))
            now = time.monotonic()


if __name__ == "__main__":
    main()
