import ConfigParser


def get_config_section():
    config = ConfigParser.RawConfigParser()
    config.readfp(open(r'config'))
    if not hasattr(get_config_section, 'section_dict'):
        get_config_section.section_dict = dict()
        for section in config.sections():
            get_config_section.section_dict[section] = dict(config.items(section))
    return get_config_section.section_dict
