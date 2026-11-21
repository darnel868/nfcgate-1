package de.robv.android.xposed;

import java.lang.reflect.Member;
import java.util.Set;

@SuppressWarnings("unused")
public final class XposedBridge {
    public static final int BOOTCLASSLOADER = 0;

    public static XC_MethodHook.Unhook hookMethod(Member method, XC_MethodHook callback) {
        return null;
    }

    public static void unhookMethod(Member method, XC_MethodHook callback) {
    }

    public static Set<XC_MethodHook.Unhook> hookAllMethods(Class<?> hookClass, String methodName, XC_MethodHook callback) {
        return null;
    }

    public static Set<XC_MethodHook.Unhook> hookAllConstructors(Class<?> hookClass, XC_MethodHook callback) {
        return null;
    }

    public static void log(String message) {
    }

    public static void log(Throwable t) {
    }
}
