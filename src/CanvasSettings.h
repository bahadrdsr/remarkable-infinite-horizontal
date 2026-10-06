#pragma once

#include <QFileSystemWatcher>
#include <QHash>
#include <QObject>
#include <QString>

class CanvasSettings : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool enabled READ enabled WRITE setEnabled NOTIFY enabledChanged)
    Q_PROPERTY(QString error READ error NOTIFY errorChanged)
    Q_PROPERTY(int revision READ revision NOTIFY revisionChanged)

public:
    enum OverrideMode { UseGlobal = 0, AlwaysInfinite = 1, AlwaysPaged = 2 };
    Q_ENUM(OverrideMode)
    explicit CanvasSettings(QString path, QObject *parent = nullptr);
    bool enabled() const { return m_enabled; }
    QString error() const { return m_error; }
    int revision() const { return m_revision; }
    void setEnabled(bool enabled);
    Q_INVOKABLE bool effectiveEnabled(const QString &documentId) const;
    Q_INVOKABLE int overrideMode(const QString &documentId) const;
    Q_INVOKABLE void setOverrideMode(const QString &documentId, int mode);

signals:
    void enabledChanged();
    void errorChanged();
    void revisionChanged();

private:
    void reload();
    bool save(bool enabled, const QHash<QString, OverrideMode> &overrides);
    void failClosed(const QString &error);
    void reportError(const QString &error);
    static QString normalizedId(const QString &documentId);
    QString m_path;
    bool m_enabled = false;
    QString m_error;
    int m_revision = 0;
    QHash<QString, OverrideMode> m_overrides;
    QFileSystemWatcher m_watcher;
};
