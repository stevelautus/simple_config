import os, sys
import logging
import errno


class InfoFilter(logging.Filter):
    def filter(self, rec):
        return rec.levelno in (logging.DEBUG, logging.INFO)

def _ensure_directory_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

def _get_local_file_logger(logger_options):
    _ensure_directory_exists(logger_options.directory)

    tgt_log_lvl = getattr(logging, logger_options.base_level.upper())

    logging.basicConfig(
        filename=os.path.join(logger_options.directory, logger_options.file_name),
        level=tgt_log_lvl,
        format=logger_options.line_format
    )

    logger = logging.getLogger(logger_options.name)
    logger.setLevel(tgt_log_lvl)
    formatter = logging.Formatter(logger_options.line_format)

    file_handler = logging.FileHandler('{0}/{1}'.format(logger_options.directory, logger_options.file_name))
    file_handler.setLevel(tgt_log_lvl)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    sh_out = logging.StreamHandler(sys.stdout)
    sh_out.setLevel(tgt_log_lvl)
    sh_out.addFilter(InfoFilter())
    sh_out.setFormatter(formatter)
    logger.addHandler(sh_out)

    sh_err = logging.StreamHandler(sys.stderr)
    sh_err.setLevel(logging.WARNING)
    sh_err.setFormatter(formatter)
    logger.addHandler(sh_err)

    return logger

def _get_stdout_logger(logger_options):
    logging.basicConfig(
        level=getattr(logging, logger_options.base_level.upper()),
        format=logger_options.line_format
    )

    return logging.getLogger(logger_options.name)


LOGGER_GETTERS_BY_TYPE = {
    "local_file": _get_local_file_logger,
    "stdout": _get_stdout_logger,
}

def init_logger(logger_type, logger_options):
    logger_getter = LOGGER_GETTERS_BY_TYPE[logger_type]
    return logger_getter(logger_options)
