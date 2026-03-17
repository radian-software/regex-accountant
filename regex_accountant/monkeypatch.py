def monkeypatch_browser_cookie3():
    """
    Fix https://github.com/borisbabic/browser_cookie3/issues/211
    """

    import browser_cookie3

    import configparser
    import glob
    import os

    def get_default_profile(user_data_path):
        config = configparser.ConfigParser()
        profiles_ini_path = glob.glob(
            os.path.join(user_data_path + "**", "profiles.ini")
        )
        fallback_path = user_data_path + "**"

        if not profiles_ini_path:
            return fallback_path

        profiles_ini_path = profiles_ini_path[0]
        config.read(profiles_ini_path, encoding="utf8")

        profile_path = None
        for section in config.sections():
            if section.startswith("Install"):
                # Use that last Install section
                profile_path = config[section].get("Default")
            # in ff 72.0.1, if both an Install section and one with Default=1 are present, the former takes precedence
            elif config[section].get("Default") == "1" and not profile_path:
                profile_path = config[section].get("Path")

        for section in config.sections():
            # the Install section has no relative/absolute info, so check the profiles
            if config[section].get("Path") == profile_path:
                absolute = config[section].get("IsRelative") == "0"
                return (
                    profile_path
                    if absolute
                    else os.path.join(os.path.dirname(profiles_ini_path), profile_path)
                )

        return fallback_path

    browser_cookie3.FirefoxBased.get_default_profile = get_default_profile
