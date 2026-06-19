class SkillError(Exception):
    status_code = 400

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class SkillNotFoundError(SkillError):
    status_code = 404


class SkillAlreadyExistsError(SkillError):
    status_code = 409
