{{- define "openclaw-agent-instance.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "openclaw-agent-instance.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else if .Values.instance.name -}}
{{- .Values.instance.name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- include "openclaw-agent-instance.name" . -}}
{{- end -}}
{{- end -}}
