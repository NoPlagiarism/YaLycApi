import requests


class AuthFailed(Exception):
    def __init__(self, login, user_exists=True):
        self.login = login
        self.user_exists = user_exists

    def __str__(self):
        if self.user_exists:
            return f"Аутентификация провалилась. Проверьте данные для пользователя {self.login}"
        return f"Аутентификация провалилась. Пользователь {self.login} не существует"


class AccessDenied(Exception):
    def __init__(self, url=''):
        self.url = url

    def __str__(self):
        return "У вас нету доступа к {}".format(self.url)


class TwoFactorNeeded(Exception):
    def __init__(self, start, lms):
        self.start = start
        self.lms = lms

    def otp_auth(self, otp):
        self.lms.auth_otp(otp, self.start)
        return self.lms


class UnknownLMSApiError(Exception):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class LMSSession(requests.Session):
    def __init__(self, login=None, password=None, cookies=None, auth_handler=None,
                 tfa_handler=None):
        super(LMSSession, self).__init__()

        self.handlers = {"AUTH": auth_handler if auth_handler else self.auth_handler,
                         "2FA": tfa_handler if tfa_handler else self.tfa_handler}

        self.user, self.password = login, password

        if cookies:
            self.import_cookies(cookies)
        else:
            self.auth_ya()
        profile_res = self.get('https://lyceum.yandex.ru/api/profile',
                               params={"withChildren": False, "withCoursesSummary": False,
                                       "withExpelled": False, "withParents": False}).json()
        self.user = profile_res['profile']['username']
        self.user_id = profile_res['profile']['id']

    def _start_auth(self) -> dict:
        auth_html = self.get("https://passport.yandex.ru/auth",
                             data={'origin': 'lyceum',
                                   'retpath': 'https://lyceum.yandex.ru/'})

        csrf_start_index = auth_html.text.index('"csrf":"') + 8
        csrf_end_index = auth_html.text[csrf_start_index:].index('"') + csrf_start_index
        csrf = auth_html.text[csrf_start_index:csrf_end_index]

        process_uuid_start = auth_html.text.index('{"process_uuid":"') + 17
        process_uuid_end = auth_html.text[process_uuid_start:].index('"') + process_uuid_start
        process_uuid = auth_html.text[process_uuid_start:process_uuid_end]

        start_raw = self.post('https://passport.yandex.ru/'
                              'registration-validations/auth/multi_step/start',
                              data={'csrf_token': csrf, "process_uuid": process_uuid,
                                    'origin': 'lyceum', 'retpath': 'https://lyceum.yandex.ru/',
                                    'login': self.user})
        start = start_raw.json()
        start['form_csrf'] = csrf
        return start

    def _auth_password(self, start: dict):
        auth_raw = self.post("https://passport.yandex.ru/"
                             "registration-validations/auth/multi_step/commit_password",
                             data={'csrf_token': start['form_csrf'], 'track_id': start['track_id'],
                                   'password': self.password,
                                   'retpath': "https://lyceum.yandex.ru/"})
        auth = auth_raw.json()

        if auth['status'] == 'error':
            if "password.not_matched" in auth['errors']:
                self.handlers["AUTH"]()
            else:
                raise UnknownLMSApiError(start_json=start, auth_json=auth, lms=self)

    def auth_otp(self, otp, start):
        self.password = otp
        self._auth_password(start)

    def auth_ya(self):
        """Аутентификация в Яндекс"""
        start = self._start_auth()
        if not start.get('can_authorize', False):
            self.handlers['AUTH'](False)
        elif start['preferred_auth_method'] == 'password' and not self.password:
            raise TypeError("Password needed")

        if 'password' in start['auth_methods']:
            self._auth_password(start)
        elif 'otp' in start['auth_methods']:
            self.handlers['2FA'](self, start)
        else:
            raise UnknownLMSApiError(start=start, lms=self)

    def get(self, *args, **kwargs):
        if kwargs.get("ConnectionRetries", 0) > 2:
            raise kwargs["ConnectionError"]
        try:
            res = requests.Session.get(self, *args, **kwargs)
        except ConnectionError as e:
            kwargs.setdefault("ConnectionRetries", 0)
            kwargs["ConnectionRetries"] += 1
            kwargs["ConnectionError"] = e
            return self.get(*args, **kwargs)
        if res.status_code == 401:
            raise AuthFailed(self.user)
        elif res.status_code == 403:
            if 'url' in kwargs:
                url = kwargs['url']
            else:
                url = args[0]
            raise AccessDenied(url)
        return res

    def post(self, *args, **kwargs):
        if kwargs.get("ConnectionRetries", 0) > 2:
            raise kwargs["ConnectionError"]
        try:
            res = requests.Session.post(self, *args, **kwargs)
        except ConnectionError as e:
            kwargs.setdefault("ConnectionRetries", 0)
            kwargs["ConnectionRetries"] += 1
            kwargs["ConnectionError"] = e
            return self.post(*args, **kwargs)
        if res.status_code == 401:
            raise AuthFailed(self.user)
        elif res.status_code == 403:
            if 'url' in kwargs:
                url = kwargs['url']
            else:
                url = args[0]
            raise AccessDenied(url)
        return res

    def export_cookies(self) -> dict:
        """Export cookies into dict"""
        return self.cookies.get_dict()

    def import_cookies(self, cookies):
        """Import cookies from dict"""
        self.cookies = requests.sessions.cookiejar_from_dict(cookies)

    def auth_handler(self, user_exists=True):
        raise AuthFailed(self.user, user_exists)

    def tfa_handler(self, start):
        """Пытается авторизоваться через введённый пароль, иначе бросает ошибку"""
        try:
            self.auth_otp(self.password, start)
        except AuthFailed:
            raise TwoFactorNeeded(start, self)

    def check_auth(self):
        r = requests.Session.get(self,
                                 "https://lyceum.yandex.ru/api/profile?withCoursesSummary=false")
        if r.status_code == 401:
            return False
        return True

    def cast_to_api(self):
        self.__class__ = LMSApi


class LMSApi(LMSSession):
    def cast_to_session(self):
        self.__class__ = LMSSession

    def get_profile(self, with_children=True, with_courses_summary=True,
                    with_expelled=True, with_parents=True):
        """Получение информации о профиле. Значение многих параметров не раскрыто"""
        res = self.get('https://lyceum.yandex.ru/api/profile/',
                       params={"withChildren": with_children,
                               "withCoursesSummary": with_courses_summary,
                               "withExpelled": with_expelled, "withParents": with_parents})
        return res.json()

    def get_notifications(self, is_read=True):
        """Получение уведомлений от Лицея.
        :type is_read: bool
        :param is_read: При значении False показывает только не прочитанные уведомления"""
        notifications = self.get('https://lyceum.yandex.ru/api/notifications',
                                 params={'isRead': is_read})
        return notifications.json()

    def get_tasks(self, course_id, limit=0):
        """Получение ВСЕХ задач из курса по course_id
        :type course_id: int or str
        :param course_id: id нужного курса
        :type limit: int
        :param limit: Ограничение на нужные задачи"""
        tasks = self.get('https://lyceum.yandex.ru/api/student/tasks',
                         params={"courseId": course_id, "limit": limit})
        return tasks.json()

    def get_task(self, task_id, group_id):
        """Получение задачи по её task_id
        :type task_id: int or str
        :param task_id: ID задачи
        :type group_id: int or str
        :param group_id: ID группы курса, из которой нужна задача"""
        task = self.get(f'https://lyceum.yandex.ru/api/student/tasks/{task_id}',
                        params={'groupId': group_id})
        return task.json()

    def get_solution(self, solution_id):
        """Получение решения по его solution_id
        :type solution_id: int or str
        :param solution_id: ID нужного решения"""
        solution = self.get(f'https://lyceum.yandex.ru/api/student/solutions/{solution_id}')
        return solution.json()

    def get_lessons(self, course_id, group_id):
        """Получение уроков определённого course_id
        :type course_id: int or str
        :param course_id: ID курса
        :type group_id: int or str
        :param group_id: ID группы курса"""
        lessons = self.get('https://lyceum.yandex.ru/api/student/lessons',
                           params={'groupId': group_id, 'courseId': course_id})
        return lessons.json()

    def get_lesson(self, lesson_id, course_id, group_id):
        """Получение урока по его lesson_id
        :type lesson_id: int or str
        :param lesson_id: ID урока
        :type course_id: int or str
        :param course_id: ID курса
        :type group_id: int or str
        :param group_id: ID группы курса"""
        lesson = self.get(f'https://lyceum.yandex.ru/api/student/lessons/{lesson_id}',
                          params={'groupId': group_id, 'courseId': course_id})
        return lesson.json()

    def get_lesson_tasks(self, lesson_id, course_id):
        """Получение задач из определённого урока с lesson_id
        :type lesson_id: int or str
        :param lesson_id: ID урока
        :type course_id: int or str
        :param course_id: ID курса"""
        lesson = self.get('https://lyceum.yandex.ru/api/student/lessonTasks',
                          params={'lessonId': lesson_id, 'courseId': course_id})
        return lesson.json()

    def get_materials(self, lesson_id):
        """Получение материалов из определённого урока с lesson_id
        :type lesson_id: int or str
        :param lesson_id: ID урока"""
        materials = self.get("https://lyceum.yandex.ru/api/materials",
                             params={'lessonId': lesson_id})
        return materials.json()

    def get_material(self, material_id, group_id, lesson_id):
        """Получение материала определённого урока через его material_id
        :type material_id: int or str
        :param material_id: ID определённого материала
        :type group_id: int or str
        :param group_id: ID группы курса
        :type lesson_id: int or str
        :param lesson_id: ID урока"""
        material = self.get(f"https://lyceum.yandex.ru/api/student/materials/{material_id}",
                            params={'groupId': group_id, 'lessonId': lesson_id})
        return material.json()


if __name__ == '__main__':
    try:
        r = LMSSession(input(), input())
    except TwoFactorNeeded as err:
        r = err.otp_auth(input("Введите одноразовый пароль: "))
    print(r.check_auth())
