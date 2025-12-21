## Plan: Implement Clash Installer

I will implement the `install` method in `src/subscribe_tool/install/install_clash.py` to handle downloading, extracting, and configuring Clash (Mihomo) and its assets.

### Steps
1.  **Import Dependencies**: Add imports for `os`, `sys`, `gzip`, `shutil`, `stat` in [src/subscribe_tool/install/install_clash.py](src/subscribe_tool/install/install_clash.py).
2.  **Define Constants**: Add default URLs for the Clash binary (Mihomo) and MMDB (Country.mmdb).
3.  **Implement `install` Method**:
    *   **Input**: Use `utils.read_input` to get the download URL, MMDB URL, and service user (defaulting to `root`). If no URL is provided, use the default constants.
    *   **Download & Extract**: Use `utils.download` to fetch the binary. Handle `.gz` extraction using `gzip` and `shutil`. Make the binary executable. if use default URL, os-arch and version should be detected automatically.
    *   **Download Assets**: Download `Country.mmdb` to the installation directory.
    *   **Generate Service File**: Read [assets/install/clash.service](assets/install/clash.service), replace variables (`%vpnuser%`, `%clash_dir%`, `%clash_exe%`) using `utils.template`, and save to the install location.
    *   **Generate Subscribe Script**: Read [assets/install/clash.subscribe.sh](assets/install/clash.subscribe.sh), replace variables (`%python_exe%`, `%repo_dir%`, `%clash_dir%`), save, and make executable.
    *   **Update Config**: Record `installed=True`, `clash_exe`, `service_file`, and `subscribe_script` paths in the `cfg` dictionary.

### Further Considerations
1.  **Platform**: The implementation assumes a Linux environment (systemd, bash) based on the existing assets.
2.  **Uninstall**: I will leave the `uninstall` method as a placeholder or basic implementation unless requested otherwise.
3.  **Paths**: I will calculate the `assets` directory path relative to the `install_clash.py` file.

I will wait for your confirmation before proceeding with the code changes.
