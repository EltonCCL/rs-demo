Since I am using tunneling, when dealing with some download task, it is advised to temporally turn off the proxy

Option A: turn proxy off only for one download command

Use this to turn proxy off only for one download command:
```bash
env -u ALL_PROXY -u all_proxy \
    -u HTTP_PROXY -u http_proxy \
    -u HTTPS_PROXY -u https_proxy \
    -u NO_PROXY -u no_proxy \
    <command>
```

or , depending on the situation, turn proxy off in the current terminal:
```bash
unset ALL_PROXY all_proxy
unset HTTP_PROXY http_proxy
unset HTTPS_PROXY https_proxy
unset NO_PROXY no_proxy
```
