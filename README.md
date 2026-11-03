# shop-coupon-automation

## Lidl Plus

```bash
uv run shop-coupon-automation lidl           # activate all inactive coupons (same as `lidl activate`)
uv run shop-coupon-automation lidl login     # log in and store tokens (uses settings.toml credentials or prompts)
uv run shop-coupon-automation lidl coupons   # list coupons, [x] = activated
```

The exit code is non-zero when login fails or any coupon could not be activated.

Tokens are stored in `$STATE_DIRECTORY/lidl_tokens.json` when run by systemd with `StateDirectory=`, otherwise in
`~/.config/shop-coupon-automation/lidl_tokens.json` (mode 0600). The access token is refreshed automatically.
When Lidl credentials are configured in `settings.toml`, the app logs in again by itself if there are no tokens or the
refresh token stops working, so no manual `lidl login` is needed on a server.

### Settings

`settings.toml` is looked up in this order (first found wins), it is optional:

1. `$CONFIGURATION_DIRECTORY/settings.toml` (set by systemd with `ConfigurationDirectory=`)
2. `./settings.toml` (working directory)
3. `~/.config/shop-coupon-automation/settings.toml`

```toml
[lidl]
email = "user@example.com"
password = "..."
```

Keep the file readable only by you (`chmod 600`), it contains a password.

### Server (systemd user service)

Example units are in `deploy/systemd/`:

```bash
uv tool install .                                  # installs ~/.local/bin/shop-coupon-automation
$EDITOR ~/.config/shop-coupon-automation/settings.toml && chmod 600 ~/.config/shop-coupon-automation/settings.toml
cp deploy/systemd/shop-coupon-automation.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now shop-coupon-automation.timer
journalctl --user -u shop-coupon-automation.service   # logs
```

The timer only runs while you are logged in unless lingering is enabled (`loginctl enable-linger`).

API constants live in `src/shop_coupon_automation/lidl/constants.py`.
Reference implementation (not a dependency): https://github.com/zsobix/lidlplus-api

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync                      # install the project and dev dependencies
uv run shop-coupon-automation --help
uv run pytest                # run tests
uv run ruff check .          # lint
uv run ruff format .         # format
uv run pyrefly check         # type check
```

### CI and releases

- `.github/workflows/ci.yml` runs on pushes to `main`, on pull requests, and on demand. It runs lint, format check,
  type check, tests, and builds the wheel, then checks that the wheel installs and runs.
- `.github/workflows/release.yml` is run manually (Actions → Release → Run workflow). Enter the version, e.g. `0.2.0`.
  It validates the version and checks that the tag does not exist yet, runs the same checks as CI, sets `version` in
  `pyproject.toml` and `uv.lock`, builds the wheel and sdist, commits the bump, creates the `vX.Y.Z` tag and publishes the
  GitHub release with the artifacts attached. Run it from `main`: the version commit is pushed to the branch the
  workflow runs on.

The release workflow pushes to the branch with the `GITHUB_TOKEN`, so branch protection must allow the Actions bot to
push, or the release fails before any tag or release is created.
