#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <json-c/json.h>

#define MAX_PATH_LEN 1024
#define JSON_FILE "/usr/share/zenith/config.json"

void run_script(const char *script_path) {
    if (fork() == 0) {  // Create child process to run the script
        execlp("python3", "python3", script_path, (char *)NULL);
        perror("execlp failed");
        exit(EXIT_FAILURE);
    }
}

int get_interval_from_json(const char *json_file) {
    struct json_object *parsed_json;
    struct json_object *interval_obj;
    int interval = 120;  // Default interval is 120 seconds

    FILE *fp = fopen(json_file, "r");
    if (fp == NULL) {
        return interval;  // Return default value if the file doesn't exist
    }

    fseek(fp, 0, SEEK_END);
    long length = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    char *data = malloc(length);
    if (data) {
        fread(data, 1, length, fp);
        fclose(fp);
    } else {
        fclose(fp);
        return interval;
    }

    parsed_json = json_tokener_parse(data);
    free(data);

    if (parsed_json == NULL) {
        return interval;  // Return default if parsing fails
    }

    if (json_object_object_get_ex(parsed_json, "interval", &interval_obj)) {
        interval = json_object_get_int(interval_obj);
    }

    json_object_put(parsed_json);
    return interval;
}

int main() {
    char script_path[MAX_PATH_LEN];
    snprintf(script_path, MAX_PATH_LEN, "%s/zenith.py", "../");

    // Get the interval from the JSON file
    int interval = get_interval_from_json(JSON_FILE);

    while (1) {
        run_script(script_path);
        sleep(interval);  // Wait for the specified interval before running again
    }

    return 0;
}
