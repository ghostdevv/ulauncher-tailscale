#!/bin/zsh
local EXTENSION_DIR="$HOME/.local/share/ulauncher/extensions/ulauncher-tailscale";

if [[ ! -e $EXTENSION_DIR ]]; then
    mkdir $EXTENSION_DIR;
fi

pnpm dlx chokidar-cli '**.{py,json,png}' --command "pkill -9 ulauncher && cp -r ./* $EXTENSION_DIR";
