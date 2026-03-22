{{- define "agent-engine.fullname" -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "agent-engine.labels" -}}
app.kubernetes.io/name: {{ include "agent-engine.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "agent-engine.image" -}}
{{ .Values.image.repository }}:{{ .Values.image.tag }}
{{- end -}}
