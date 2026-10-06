#include "CanvasSettings.h"
#include <QFile>
#include <QTemporaryDir>
#include <QSignalSpy>
#include <QtTest>

class SettingsTests : public QObject
{
    Q_OBJECT
private slots:
    void defaultsOnAndPersistsToggle()
    {
        QTemporaryDir root;
        QVERIFY(root.isValid());
        const auto path = root.filePath(QStringLiteral("settings.json"));
        CanvasSettings settings(path);
        QVERIFY(settings.enabled());
        QVERIFY(settings.error().isEmpty());
        settings.setEnabled(false);
        QVERIFY(!settings.enabled());
        CanvasSettings reopened(path);
        QVERIFY(!reopened.enabled());
        reopened.setEnabled(true);
        QTRY_VERIFY(settings.enabled());
        QVERIFY(settings.effectiveEnabled(QStringLiteral("00000000-1111-2222-3333-444444444444")));
    }

    void malformedSettingsFailClosedWithoutOverwrite()
    {
        QTemporaryDir root;
        const auto path = root.filePath(QStringLiteral("settings.json"));
        QFile file(path);
        QVERIFY(file.open(QIODevice::WriteOnly));
        file.write("{broken");
        file.close();
        CanvasSettings settings(path);
        QVERIFY(!settings.enabled());
        QVERIFY(!settings.error().isEmpty());
        QVERIFY(file.open(QIODevice::ReadOnly));
        QCOMPARE(file.readAll(), QByteArray("{broken"));
        file.close();
        settings.setEnabled(true);
        QVERIFY(settings.enabled());
        QVERIFY(settings.error().isEmpty());
    }

    void saveFailureDoesNotPretendSuccess()
    {
        QTemporaryDir root;
        const auto path = root.filePath(QStringLiteral("settings.json"));
        CanvasSettings settings(path);
        QVERIFY(settings.enabled());
        QVERIFY(QFile::remove(path));
        QVERIFY(QDir().mkdir(path));
        settings.setEnabled(false);
        QVERIFY(settings.enabled());
        QVERIFY(!settings.error().isEmpty());
    }

    void unsupportedVersionFailsClosed()
    {
        QTemporaryDir root;
        const auto path = root.filePath(QStringLiteral("settings.json"));
        QFile file(path);
        QVERIFY(file.open(QIODevice::WriteOnly));
        file.write("{\"version\":2,\"enabled\":true}");
        file.close();
        CanvasSettings settings(path);
        QVERIFY(!settings.enabled());
        QVERIFY(!settings.error().isEmpty());
    }

    void malformedReloadClearsAnExistingOverride()
    {
        QTemporaryDir root;
        const auto path = root.filePath(QStringLiteral("settings.json"));
        const QString id = QStringLiteral("00000000-1111-2222-3333-444444444444");
        CanvasSettings settings(path);
        settings.setOverrideMode(id, CanvasSettings::AlwaysInfinite);
        QVERIFY(settings.effectiveEnabled(id));
        QFile file(path);
        QVERIFY(file.open(QIODevice::WriteOnly | QIODevice::Truncate));
        file.write("{invalid");
        file.close();
        QTRY_VERIFY(!settings.enabled());
        QTRY_COMPARE(settings.overrideMode(id), int(CanvasSettings::UseGlobal));
        QVERIFY(!settings.effectiveEnabled(id));
    }

    void notebookOverridesCanForceEitherMode()
    {
        QTemporaryDir root;
        const auto path = root.filePath(QStringLiteral("settings.json"));
        const QString id = QStringLiteral("00000000-1111-2222-3333-444444444444");
        CanvasSettings settings(path);
        QCOMPARE(settings.overrideMode(id), int(CanvasSettings::UseGlobal));
        QVERIFY(settings.effectiveEnabled(id));
        settings.setOverrideMode(id, CanvasSettings::AlwaysPaged);
        QCOMPARE(settings.overrideMode(id), int(CanvasSettings::AlwaysPaged));
        QVERIFY(!settings.effectiveEnabled(id));
        settings.setEnabled(false);
        settings.setOverrideMode(QStringLiteral("{") + id.toUpper() + QStringLiteral("}"),
                                 CanvasSettings::AlwaysInfinite);
        QCOMPARE(settings.overrideMode(id), int(CanvasSettings::AlwaysInfinite));
        QVERIFY(settings.effectiveEnabled(id));
        CanvasSettings reopened(path);
        QCOMPARE(reopened.overrideMode(id), int(CanvasSettings::AlwaysInfinite));
        reopened.setOverrideMode(id, CanvasSettings::UseGlobal);
        QCOMPARE(reopened.overrideMode(id), int(CanvasSettings::UseGlobal));
        QVERIFY(!reopened.effectiveEnabled(id));
    }

    void invalidNotebookOverrideDoesNotChangeState()
    {
        QTemporaryDir root;
        CanvasSettings settings(root.filePath(QStringLiteral("settings.json")));
        const int revision = settings.revision();
        settings.setOverrideMode(QStringLiteral("not-a-uuid"), CanvasSettings::AlwaysPaged);
        QCOMPARE(settings.revision(), revision);
        QVERIFY(!settings.error().isEmpty());
    }
};

QTEST_GUILESS_MAIN(SettingsTests)
#include "SettingsTests.moc"
