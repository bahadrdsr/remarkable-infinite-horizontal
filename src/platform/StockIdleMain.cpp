#include "StockActivity.h"

#include <QCoreApplication>
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QTextStream>
#include <QThread>

using namespace infinitehorizontal;

static bool readActivity(const QString &process, StockActivity &activity, QString &error)
{
    QFile name(process + QStringLiteral("/comm"));
    if (!name.open(QIODevice::ReadOnly) || name.readAll().trimmed() != QByteArrayLiteral("xochitl")) {
        error = QStringLiteral("The expected stock process is no longer present.");
        return false;
    }
    const QDir tasks(process + QStringLiteral("/task"));
    const QStringList threads = tasks.entryList(QDir::Dirs | QDir::NoDotAndDotDot, QDir::Name);
    if (threads.isEmpty()) {
        error = QStringLiteral("Cannot enumerate the stock application's threads.");
        return false;
    }
    activity = {};
    for (const auto &thread : threads) {
        QFile stat(tasks.filePath(thread + QStringLiteral("/stat")));
        if (!stat.open(QIODevice::ReadOnly)) {
            error = QStringLiteral("Stock thread state changed during the check. Retry after it settles.");
            return false;
        }
        const auto parsed = parseThreadActivity(stat.readAll());
        if (!parsed) {
            error = QStringLiteral("Cannot parse stock thread activity.");
            return false;
        }
        activity.identities.push_back(thread + QStringLiteral(":") + QString::number(parsed->started));
        activity.ticks += parsed->ticks;
        // Sleeping/idle threads are acceptable; uninterruptible I/O is not quiet.
        activity.running |= parsed->state != 'S' && parsed->state != 'I';
    }
    return true;
}

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    QTextStream out(stdout), error(stderr);
    bool valid = false;
    const QStringList args = app.arguments();
    const auto pid = args.size() == 2 ? args[1].toULongLong(&valid) : 0;
    if (!valid || pid < 2) {
        error << "Expected the current Xochitl PID.\n";
        return 2;
    }
    const QString process = QStringLiteral("/proc/") + QString::number(pid);
    QuietWindow quiet(600);
    QElapsedTimer elapsed;
    elapsed.start();
    while (elapsed.elapsed() < 10000) {
        StockActivity activity;
        QString message;
        if (!readActivity(process, activity, message)) {
            if (message == QStringLiteral("Stock thread state changed during the check. Retry after it settles.")) {
                QThread::msleep(50);
                continue;
            }
            error << message << '\n';
            return 1;
        }
        if (quiet.observe(activity, elapsed.elapsed())) {
            out << "Stock process " << pid << " had 600 ms of quiet thread activity.\n";
            return 0;
        }
        QThread::msleep(50);
    }
    error << "Stock application remained busy for 10 seconds. Refusing to stop it.\n";
    return 1;
}
