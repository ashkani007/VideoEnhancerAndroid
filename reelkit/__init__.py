"""ReelKit — autonomous storytelling Shorts producer.

Pipeline stages (each cached, each resumable):

    discover -> acquire -> analyze -> write -> voice -> edit -> render(preview)
                                                              -> [approval] -> render(final)
"""

__version__ = "0.1.0"
