# YaLycApi
## Оставим поколение будущим лицеистам
> Что я сказал?

Файл [api/YandexLyceum.py](api/YandexLyceum.py)
Класс `LMSSession` принимаует при инициализации логин и пароль. Также 2 перехватчика ошибок:
 - auth_handler - перехватчик ошибок, связанных с аутентификацией
 - tfa_handler - перехватчик двухфакторной аутентификации. Класс TwoFactorNeeded имеет функцию otp_auth, которая позволяет перепройти аутентификацию с паролем, передающимся в функцию
Сам класс `LMSSession` представляет собой сессию requests.Session. Чтобы преобразить данный класс в LMSApi, используйте LMSSession.cast_to_api()

Класс `LMSApi` представляет собой класс `LMSSession`, дополненный методами обращения к апи Яндекс Лицея.

 - get_profile(with_children=True, with_courses_summary=True, with_expelled=True, with_parents=True) - Получение информации о профиле
   - with_courses_summary - С информацией о курсах или нет
   - with_expelled - С законченными или исключёнными курсами
   - *with_children - с детьми? (Наверное речь о родительском аккаунте)*
   - *with_parents - с родителями? (Опять же речь об аккаунте, к которому привязан родитель. Наверное)*
 - get_notifications(is_read=True). Получение всех уведомлений
   - is_read - Показывать все уведомления, даже прочитанные
 - get_tasks(course_id, limit=0). Получить все доступные задачи курса с id - course_id
   - course_id - ID курса
   - limit - лимит выдаваемых задач, при нуле выдаёт абсолютно все задачи
 - get_task(task_id, group_id). Получить задачу по её ID
   - task_id - ID задачи
   - group_id - ID группы, в которой существует пользователь и которой предоставлен доступ к курсу с этой задачей
 - get_solution(solution). Получение решения по его solution_id
   - solution_id - ID нужного решения пользователя
 - get_lessons(course_id, group_id). Получение уроков определённого course_id
   - course_id - ID курса
   - group_id - ID группы курса
 - get_lesson_tasks(lesson_id, course_id). Получение задач из определённого урока с lesson_id
   - lesson_id - ID урока
   - course_id - ID курса
 - get_materials(lesson_id). Получение материалов из определённого урока с lesson_id
   - lesson_id - ID урока
 - get_material(material_id, group_id, lesson_id). Получение материала определённого урока через его material_id
   - material_id - ID определённого материала
   - group_id - ID группы курса
   - lesson_id - ID урока
