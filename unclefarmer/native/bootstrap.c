/* Stable front door. Imports only Windows system DLLs, never the application runtime.
 * Update protocol v1 deliberately never replaces this executable. */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <wchar.h>
#include <stdio.h>

#define CAP 32768
/* updater.LAUNCHER_MARKER: how an update tells this front door from an older copy's Nuitka exe. */
__attribute__((used)) static const char launcher_marker[] = "UNCLEFARMER-NATIVE-LAUNCHER-1";
static wchar_t root[CAP], path[CAP], command[CAP * 2];

static int safe_path(const wchar_t *value) {
    wchar_t buffer[CAP];
    if (wcslen(value) >= CAP) return 0;
    wcscpy(buffer, value);
    for (wchar_t *p = buffer + 3; ; ++p) {
        if (*p == L'\\' || *p == 0) {
            wchar_t saved = *p;
            *p = 0;
            DWORD attr = GetFileAttributesW(buffer);
            *p = saved;
            if (attr != INVALID_FILE_ATTRIBUTES && (attr & FILE_ATTRIBUTE_REPARSE_POINT)) return 0;
            if (saved == 0) break;
        }
    }
    return 1;
}

static DWORD run(const wchar_t *exe, const wchar_t *args, const wchar_t *working) {
    STARTUPINFOW si = {0};
    PROCESS_INFORMATION pi = {0};
    si.cb = sizeof(si);
    if (!safe_path(exe)) return ERROR_CANT_ACCESS_FILE;
    if (swprintf(command, CAP * 2, L"\"%ls\" %ls", exe, args) < 0) return ERROR_BUFFER_OVERFLOW;
    if (!CreateProcessW(exe, command, NULL, NULL, FALSE, 0, NULL, working, &si, &pi)) return GetLastError();
    CloseHandle(pi.hThread);
    DWORD result = ERROR_GEN_FAILURE;
    if (WaitForSingleObject(pi.hProcess, INFINITE) == WAIT_OBJECT_0) GetExitCodeProcess(pi.hProcess, &result);
    CloseHandle(pi.hProcess);
    return result;
}

static void recovery_failure(DWORD code) {
    wchar_t log[CAP];
    char text[256];
    swprintf(log, CAP, L"%ls\\.recovery\\bootstrap-error-%lu-%llu.txt", root,
             (unsigned long)GetCurrentProcessId(), (unsigned long long)GetTickCount64());
    if (!safe_path(log)) return;
    HANDLE file = CreateFileW(log, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_NEW,
                              FILE_ATTRIBUTE_NORMAL | FILE_FLAG_WRITE_THROUGH, NULL);
    if (file == INVALID_HANDLE_VALUE) return;
    int length = snprintf(text, sizeof(text),
        "Recovery runtime .recovery/runtime/UncleFarmerApp.exe failed with Windows/process code %lu. "
        "The main application was not launched; preserve the journals and backups.\r\n", (unsigned long)code);
    DWORD written;
    if (length > 0 && length < (int)sizeof(text)) WriteFile(file, text, (DWORD)length, &written, NULL);
    FlushFileBuffers(file);
    CloseHandle(file);
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, LPWSTR args, int show) {
    (void)instance; (void)previous; (void)show;
    DWORD n = GetModuleFileNameW(NULL, root, CAP);
    if (!n || n >= CAP || !safe_path(root)) return ERROR_BAD_PATHNAME;
    wchar_t *slash = wcsrchr(root, L'\\');
    if (!slash) return ERROR_BAD_PATHNAME;
    *slash = 0;
    if (wcslen(root) + 128 >= CAP) return ERROR_BUFFER_OVERFLOW;
    swprintf(path, CAP, L"%ls\\.recovery\\transaction.json", root);
    DWORD journal = GetFileAttributesW(path);
    DWORD error = GetLastError();
    int pending = journal != INVALID_FILE_ATTRIBUTES || (error != ERROR_FILE_NOT_FOUND && error != ERROR_PATH_NOT_FOUND);
    swprintf(path, CAP, L"%ls\\.recovery\\transaction.json.prev", root);
    if (GetFileAttributesW(path) != INVALID_FILE_ATTRIBUTES) pending = 1;
    else if (GetLastError() != ERROR_FILE_NOT_FOUND && GetLastError() != ERROR_PATH_NOT_FOUND) pending = 1;
    swprintf(path, CAP, L"%ls\\.recovery\\armed", root);
    if (GetFileAttributesW(path) != INVALID_FILE_ATTRIBUTES) pending = 1;
    else if (GetLastError() != ERROR_FILE_NOT_FOUND && GetLastError() != ERROR_PATH_NOT_FOUND) pending = 1;
    if (pending) {
        wchar_t recovery_args[CAP + 64];
        wchar_t recovery_directory[CAP];
        swprintf(path, CAP, L"%ls\\.recovery\\runtime\\UncleFarmerApp.exe", root);
        swprintf(recovery_directory, CAP, L"%ls\\.recovery\\runtime", root);
        swprintf(recovery_args, CAP + 64, L"--recover-update \"%ls\"", root);
        DWORD result = run(path, recovery_args, recovery_directory);
        if (result) {
            recovery_failure(result);
            return (int)result; /* Fail closed. Never launch a mixed installation. */
        }
    }
    swprintf(path, CAP, L"%ls\\UncleFarmerApp.exe", root);
    return (int)run(path, args, root);
}
