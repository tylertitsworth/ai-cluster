{{- define "langgraph-serve.fullname" -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "langgraph-serve.labels" -}}
app.kubernetes.io/name: {{ include "langgraph-serve.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "langgraph-serve.image" -}}
{{ .Values.image.repository }}:{{ .Values.image.tag }}
{{- end -}}
