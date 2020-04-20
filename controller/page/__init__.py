from . import view, api, ocr, task

views = [
    view.PageListHandler, view.PageBrowseHandler, view.PageViewHandler, view.PageInfoHandler,
    view.PageBoxHandler, view.PageOrderHandler, view.PageCmpTxtHandler,
    view.PageTxtHandler, view.PageTextHandler,
    task.PageTaskAdminHandler, task.PageTaskStatHandler, task.PageTaskResumeHandler,
    task.PageCutTaskHandler, task.PageTxtTaskHandler,
]

handlers = [
    ocr.FetchTasksApi, ocr.SubmitTasksApi, ocr.ConfirmFetchApi,
    api.PageDeleteApi, api.PageUpsertApi,
    api.PageBoxApi, api.PageOrderApi, api.PageCmpTxtApi, api.PageCmpTxtNeighborApi,
    api.PageTxtDiffApi, api.PageDetectCharsApi, api.PageExportCharsApi, api.PageSourceApi,
    task.PageTaskPublishApi, task.PageCutTaskApi,
]

modules = {'TextArea': view.TextArea}
