class Singleton(type):
    def __init__(cls, name, bases, dct):
        super(Singleton, cls).__init__(name, bases, dct)
        cls._SINGLETON = None
    
    def __call__(cls, *args, **kwargs):
        if cls._SINGLETON is None:
            cls._SINGLETON = super(Singleton, cls).__call__(*args, **kwargs)

        return cls._SINGLETON
